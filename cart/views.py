import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from core.models import Dish
from . import service
from .models import Wishlist


# ---------- helpers ----------

def _available_dish_or_none(dish_id):
    try:
        return Dish.objects.select_related('restaurant', 'category').get(
            pk=int(dish_id), is_available=True, restaurant__is_active=True)
    except (Dish.DoesNotExist, TypeError, ValueError):
        return None


def _bundle(request, message=None, **extra):
    """Standard AJAX payload: fresh HTML for every cart UI surface + totals."""
    lines, totals = service.get_lines(request)
    ctx = {'lines': lines, 'totals': totals}
    payload = {
        'ok': True,
        'message': message,
        'cart_count': totals['count'],
        'sidebar_html': render_to_string('cart/includes/sidebar.html', ctx, request),
        'lines_html': render_to_string('cart/includes/lines.html', ctx, request),
        'summary_html': render_to_string('cart/includes/summary.html', ctx, request),
        'totals': {k: str(v) for k, v in totals.items()
                   if k not in ('coupon', 'coupon_error', 'is_empty')},
        'is_empty': totals['is_empty'],
    }
    payload.update(extra)
    return JsonResponse(payload)


def _error(message, status=400, **extra):
    return JsonResponse({'ok': False, 'message': message, **extra}, status=status)


def _dish_from_request(request):
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = request.POST
    return body, _available_dish_or_none(body.get('dish_id'))


# ---------- pages ----------

def cart_page(request):
    lines, totals = service.get_lines(request)
    return render(request, 'cart/cart.html', {'lines': lines, 'totals': totals})


def wishlist_page(request):
    dishes = Dish.objects.none()
    if request.user.is_authenticated:
        dishes = (
            Dish.objects
            .filter(wishlisted_by__user=request.user,
                    is_available=True, restaurant__is_active=True)
            .select_related('restaurant', 'category')
            .order_by('-wishlisted_by__added_at')
        )
    return render(request, 'cart/wishlist.html', {'wishlist_dishes': dishes})


# ---------- cart AJAX ----------

@require_POST
def cart_add(request):
    body, dish = _dish_from_request(request)
    if dish is None:
        return _error('Sorry, this dish is no longer available. 😕')
    qty = body.get('quantity', 1)
    try:
        qty = max(1, min(int(qty), service.MAX_QTY_PER_DISH))
    except (TypeError, ValueError):
        qty = 1
    service.add_item(request, dish, qty)
    return _bundle(request, message=f'{dish.name} added to cart! 🎉')


@require_POST
def cart_update(request):
    body, dish = _dish_from_request(request)
    if dish is None:
        return _error('Sorry, this dish is no longer available. 😕')
    try:
        qty = int(body.get('quantity', 1))
    except (TypeError, ValueError):
        qty = 1
    if qty <= 0:
        service.remove_item(request, dish)
        return _bundle(request, message=f'{dish.name} removed from cart.')
    service.set_quantity(request, dish, qty)
    return _bundle(request)


@require_POST
def cart_remove(request):
    body, dish = _dish_from_request(request)
    if dish is None:
        return _error('Sorry, this dish is no longer available. 😕')
    service.remove_item(request, dish)
    return _bundle(request, message=f'{dish.name} removed from cart.')


@require_POST
def coupon_apply(request):
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = request.POST
    ok, coupon, message = service.apply_coupon(request, body.get('code', ''))
    if not ok:
        # still 200 + ok:false so the JS toast shows the friendly message
        payload = json.loads(_bundle(request).content)
        payload.update({'ok': False, 'message': message})
        return JsonResponse(payload)
    return _bundle(request, message=message)


@require_POST
def coupon_remove(request):
    service.remove_coupon(request)
    return _bundle(request, message='Coupon removed.')


# ---------- wishlist AJAX ----------

@require_POST
def wishlist_toggle(request):
    if not request.user.is_authenticated:
        return JsonResponse({
            'ok': False, 'requires_login': True,
            'message': 'Please sign in to build your wishlist ❤️',
        })
    body, dish = _dish_from_request(request)
    if dish is None:
        return _error('Sorry, this dish is no longer available. 😕')
    now_wishlisted = service.toggle_wishlist(request.user, dish)
    return JsonResponse({
        'ok': True,
        'wishlisted': now_wishlisted,
        'message': (f'{dish.name} saved to wishlist ❤️' if now_wishlisted
                    else f'{dish.name} removed from wishlist.'),
    })
