"""
Cart service — one API over two storage modes:

* logged-in user  -> cart.Cart / cart.CartItem in the database
* guest           -> plain dict in the session: {'cart': {'<dish_id>': qty}}

Every view/AJAX endpoint calls these helpers and never touches storage directly.
On login, merge_session_cart() folds the guest cart into the user's DB cart.
"""
from decimal import Decimal

from django.conf import settings as django_settings

from core.models import Coupon, Dish
from .models import Cart, CartItem

# ---- pricing rules (single source of truth) ----
DELIVERY_FEE = Decimal('40.00')
FREE_DELIVERY_ABOVE = Decimal('499.00')
TAX_RATE = Decimal('0.05')          # 5% GST
MAX_QTY_PER_DISH = 20

SESSION_KEY = 'cart'
COUPON_SESSION_KEY = 'coupon_code'


# ---------- low-level storage helpers ----------

def _get_db_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _get_session_map(request):
    return request.session.get(SESSION_KEY, {})


def _save_session_map(request, mapping):
    if mapping:
        request.session[SESSION_KEY] = mapping
    else:
        request.session.pop(SESSION_KEY, None)
    request.session.modified = True


# ---------- mutations (mode-agnostic) ----------

def add_item(request, dish, quantity=1):
    quantity = max(1, min(int(quantity), MAX_QTY_PER_DISH))
    if request.user.is_authenticated:
        item, created = CartItem.objects.get_or_create(
            cart=_get_db_cart(request.user), dish=dish,
            defaults={'quantity': quantity})
        if not created:
            item.quantity = min(item.quantity + quantity, MAX_QTY_PER_DISH)
            item.save(update_fields=['quantity'])
    else:
        mapping = _get_session_map(request)
        key = str(dish.pk)
        mapping[key] = min(int(mapping.get(key, 0)) + quantity, MAX_QTY_PER_DISH)
        _save_session_map(request, mapping)


def set_quantity(request, dish, quantity):
    """Set exact quantity; <= 0 removes the line."""
    if request.user.is_authenticated:
        CartItem.objects.filter(cart=_get_db_cart(request.user), dish=dish).delete() \
            if quantity <= 0 else None
        if quantity > 0:
            CartItem.objects.update_or_create(
                cart=_get_db_cart(request.user), dish=dish,
                defaults={'quantity': min(int(quantity), MAX_QTY_PER_DISH)})
    else:
        mapping = _get_session_map(request)
        key = str(dish.pk)
        if quantity <= 0:
            mapping.pop(key, None)
        else:
            mapping[key] = min(int(quantity), MAX_QTY_PER_DISH)
        _save_session_map(request, mapping)


def remove_item(request, dish):
    set_quantity(request, dish, 0)


def merge_session_cart(user, session):
    """Fold a guest's session cart into the user's DB cart (called on login)."""
    mapping = session.pop(SESSION_KEY, None)
    session.modified = True
    if not mapping:
        return
    cart = _get_db_cart(user)
    for dish_id, qty in mapping.items():
        dish = Dish.objects.filter(pk=dish_id, is_available=True,
                                 restaurant__is_active=True).first()
        if not dish:
            continue
        item, created = CartItem.objects.get_or_create(
            cart=cart, dish=dish, defaults={'quantity': int(qty)})
        if not created:
            item.quantity = min(item.quantity + int(qty), MAX_QTY_PER_DISH)
            item.save(update_fields=['quantity'])


def clear(request):
    if request.user.is_authenticated:
        CartItem.objects.filter(cart=_get_db_cart(request.user)).delete()
    else:
        _save_session_map(request, {})


# ---------- reads ----------

def get_lines(request):
    """Return (lines, totals). Lines: [{'dish', 'quantity', 'sub_total'} ...]"""
    if request.user.is_authenticated:
        items = (
            CartItem.objects
            .filter(cart=_get_db_cart(request.user),
                    dish__is_available=True, dish__restaurant__is_active=True)
            .select_related('dish__restaurant', 'dish__category')
        )
        lines = [{'dish': i.dish, 'quantity': i.quantity, 'sub_total': i.sub_total}
                 for i in items]
    else:
        mapping = _get_session_map(request)
        dishes = {
            d.pk: d for d in
            Dish.objects.filter(pk__in=[int(k) for k in mapping] or [0],
                                is_available=True, restaurant__is_active=True)
            .select_related('restaurant', 'category')
        }
        lines = [{'dish': d, 'quantity': q, 'sub_total': d.effective_price * q}
                 for k, q in mapping.items()
                 if (d := dishes.get(int(k)))]

    lines.sort(key=lambda l: (-l['dish'].is_bestseller, l['dish'].name))
    return lines, compute_totals(request, lines)


def compute_totals(request, lines):
    subtotal = sum((l['sub_total'] for l in lines), Decimal('0.00'))
    count = sum(l['quantity'] for l in lines)

    delivery = Decimal('0.00')
    if subtotal and subtotal < FREE_DELIVERY_ABOVE:
        delivery = DELIVERY_FEE

    coupon, coupon_error = get_applied_coupon(request)
    discount = coupon.get_discount_value(subtotal) if coupon else Decimal('0.00')

    tax = ((subtotal - discount) * TAX_RATE).quantize(Decimal('0.01'))
    total = subtotal - discount + delivery + tax

    prep_times = [l['dish'].preparation_time for l in lines]
    eta = max(prep_times) + 10 if prep_times else 0

    return {
        'count': count,
        'subtotal': subtotal,
        'delivery': delivery,
        'free_delivery_above': FREE_DELIVERY_ABOVE,
        'to_free_delivery': max(FREE_DELIVERY_ABOVE - subtotal, Decimal('0.00')),
        'coupon': coupon,
        'coupon_error': coupon_error,
        'discount': discount,
        'tax': tax,
        'total': total,
        'eta': eta,
        'is_empty': not lines,
    }


# ---------- coupon ----------

def get_applied_coupon(request):
    """Return (coupon|None, error|None) for the coupon code stored in the session."""
    code = request.session.get(COUPON_SESSION_KEY)
    if not code:
        return None, None
    coupon = Coupon.objects.filter(code__iexact=code).first()
    if coupon is None:
        return None, 'This coupon code is not valid.'
    if not coupon.is_valid_now:
        return None, 'This coupon has expired.'
    return coupon, None


def apply_coupon(request, code):
    """Validate + store a coupon code. Returns (ok, coupon|None, message)."""
    code = (code or '').strip().upper()
    coupon = Coupon.objects.filter(code__iexact=code).first() if code else None
    if coupon is None:
        return False, None, f'"{code}" is not a valid coupon code.'
    if not coupon.is_valid_now:
        return False, None, f'"{coupon.code}" has expired.'
    lines, totals = get_lines(request)
    if totals['subtotal'] < coupon.min_order_amount:
        return False, None, (
            f'Add ₹{coupon.min_order_amount - totals["subtotal"]:g} more — '
            f'{coupon.code} needs a minimum order of ₹{coupon.min_order_amount:g}.')
    request.session[COUPON_SESSION_KEY] = coupon.code
    request.session.modified = True
    return True, coupon, f'Coupon {coupon.code} applied — you saved ₹{coupon.get_discount_value(totals["subtotal"]):g}! 🎉'


def remove_coupon(request):
    request.session.pop(COUPON_SESSION_KEY, None)
    request.session.modified = True


# ---------- wishlist ----------

def wishlist_ids_for(request):
    """Set of dish ids the current user has wishlisted (empty for guests)."""
    if not request.user.is_authenticated:
        return set()
    return set(request.user.wishlist_items.values_list('dish_id', flat=True))


def toggle_wishlist(user, dish):
    """Returns True if the dish is now wishlisted, False if removed."""
    entry, created = None, False
    from .models import Wishlist
    entry = Wishlist.objects.filter(user=user, dish=dish).first()
    if entry:
        entry.delete()
        return False
    Wishlist.objects.create(user=user, dish=dish)
    return True
