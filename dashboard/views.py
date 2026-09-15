"""Custom QuickBite control panel — staff dashboard + restaurant owner panel.

Deliberately separate from django.contrib.admin: orange-themed UI, Chart.js
graphs, one-click status updates, scoped owner views.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Category, Coupon, Dish, Restaurant
from orders.models import Order, OrderItem
from orders.service import send_status_update_email
from reviews.models import Review

from .forms import CategoryForm, CouponForm, DishForm, RestaurantForm

User = get_user_model()
ACTIVE = Order.Status.CANCELLED  # excluded from revenue


# ---------- stats helpers ----------

def _money(qs):
    return qs.exclude(status=ACTIVE).aggregate(s=Sum('total'))['s'] or 0


def _daily_series(days=14):
    """[(date, revenue, order_count)] for the last `days` days, gaps filled."""
    start = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        Order.objects.exclude(status=ACTIVE)
        .filter(created_at__date__gte=start)
        .annotate(d=TruncDate('created_at'))
        .values('d').annotate(rev=Sum('total'), n=Count('id'))
    )
    by_day = {r['d']: r for r in rows}
    return [
        {
            'date': (start + timedelta(days=i)).strftime('%d %b'),
            'revenue': float(by_day.get(start + timedelta(days=i), {}).get('rev') or 0),
            'orders': by_day.get(start + timedelta(days=i), {}).get('n', 0),
        }
        for i in range(days)
    ]


# ============================================================
# STAFF DASHBOARD
# ============================================================

@staff_member_required
def home(request):
    today = timezone.localdate()
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)

    status_rows = Order.objects.values('status').annotate(n=Count('id'))
    status_map = {r['status']: r['n'] for r in status_rows}

    top_dishes = (
        OrderItem.objects.exclude(order__status=ACTIVE)
        .values('dish_name')
        .annotate(qty=Sum('quantity'))
        .order_by('-qty')[:5]
    )

    chart_data = {
        'daily': _daily_series(14),
        'statuses': [{'label': Order.Status(s).label, 'value': status_map.get(s, 0)}
                     for s in Order.Status.values],
        'top_dishes': [{'name': d['dish_name'], 'qty': d['qty']} for d in top_dishes],
    }

    return render(request, 'dashboard/home.html', {
        'orders_today': Order.objects.filter(created_at__date=today).count(),
        'orders_week': Order.objects.filter(created_at__date__gte=week_ago).count(),
        'orders_month': Order.objects.filter(created_at__date__gte=month_start).count(),
        'orders_total': Order.objects.count(),
        'revenue_total': _money(Order.objects.all()),
        'revenue_today': _money(Order.objects.filter(created_at__date=today)),
        'revenue_month': _money(Order.objects.filter(created_at__date__gte=month_start)),
        'users_total': User.objects.count(),
        'users_month': User.objects.filter(date_joined__date__gte=month_start).count(),
        'restaurants_total': Restaurant.objects.count(),
        'dishes_total': Dish.objects.count(),
        'reviews_total': Review.objects.count(),
        'chart_data': chart_data,
        'recent_orders': Order.objects.select_related('user', 'address')[:8],
        'flagged_reviews': Review.objects.filter(reported=True, is_approved=True).count(),
    })


# ---------- orders ----------

@staff_member_required
def orders_list(request):
    qs = Order.objects.select_related('user', 'address')
    status = request.GET.get('status', '')
    if status in Order.Status.values:
        qs = qs.filter(status=status)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(order_id__icontains=q) | Q(user__username__icontains=q) |
                       Q(user__email__icontains=q))
    page = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'dashboard/orders.html', {
        'page_obj': page, 'status_choices': Order.Status.choices,
        'current_status': status, 'q': q,
        'revenue': _money(qs),
    })


@staff_member_required
def order_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('user', 'address').prefetch_related('items'),
        order_id=order_id)
    return render(request, 'dashboard/order_detail.html', {
        'order': order, 'status_choices': Order.Status.choices,
    })


@staff_member_required
@require_POST
def order_status_update(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    new_status = request.POST.get('status')
    if new_status not in Order.Status.values:
        messages.error(request, 'Unknown status.')
    elif new_status != order.status:
        order.status = new_status
        if new_status == Order.Status.DELIVERED and not order.delivered_at:
            order.delivered_at = timezone.now()
        order.save()
        send_status_update_email(order)
        messages.success(request, f'{order.order_id} → {order.get_status_display()} ✅')
    nxt = request.POST.get('next')
    return redirect(nxt) if nxt else redirect('dashboard:order_view', order_id=order.order_id)


# ---------- CRUD: restaurants / dishes / categories / coupons ----------

@staff_member_required
def restaurants_list(request):
    qs = Restaurant.objects.annotate(dish_count=Count('dishes'))
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(cuisine_type__icontains=q))
    return render(request, 'dashboard/restaurants.html', {
        'restaurants': qs, 'q': q,
        'cuisine_choices': Restaurant.CUISINE_CHOICES,
    })


@staff_member_required
def restaurant_form(request, pk=None):
    restaurant = get_object_or_404(Restaurant, pk=pk) if pk else None
    form = RestaurantForm(request.POST or None, request.FILES or None, instance=restaurant)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Restaurant {"updated" if restaurant else "created"} ✅')
        return redirect('dashboard:restaurants')
    return render(request, 'dashboard/form.html', {
        'form': form,
        'title': f'Edit {restaurant.name}' if restaurant else 'New restaurant',
        'back_url': 'dashboard:restaurants',
    })


@staff_member_required
@require_POST
def restaurant_delete(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)
    name = restaurant.name
    restaurant.delete()
    messages.success(request, f'Restaurant "{name}" deleted.')
    return redirect('dashboard:restaurants')


@staff_member_required
@require_POST
def restaurant_toggle(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)
    restaurant.is_active = not restaurant.is_active
    restaurant.save(update_fields=['is_active'])
    messages.info(request, f'{restaurant.name} is now {"ACTIVE" if restaurant.is_active else "HIDDEN"}.')
    return redirect('dashboard:restaurants')


@staff_member_required
def dishes_list(request):
    qs = Dish.objects.select_related('restaurant', 'category')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(restaurant__name__icontains=q))
    restaurant = request.GET.get('restaurant', '')
    if restaurant:
        qs = qs.filter(restaurant_id=restaurant)
    category = request.GET.get('category', '')
    if category:
        qs = qs.filter(category_id=category)
    page = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'dashboard/dishes.html', {
        'page_obj': page, 'q': q,
        'restaurants': Restaurant.objects.order_by('name'),
        'categories': Category.objects.order_by('name'),
        'cur_restaurant': restaurant, 'cur_category': category,
    })


@staff_member_required
def dish_form(request, pk=None):
    dish = get_object_or_404(Dish, pk=pk) if pk else None
    form = DishForm(request.POST or None, request.FILES or None, instance=dish)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Dish {"updated" if dish else "created"} ✅')
        return redirect('dashboard:dishes')
    return render(request, 'dashboard/form.html', {
        'form': form,
        'title': f'Edit {dish.name}' if dish else 'New dish',
        'back_url': 'dashboard:dishes',
    })


@staff_member_required
@require_POST
def dish_delete(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    name = dish.name
    dish.delete()
    messages.success(request, f'Dish "{name}" deleted.')
    return redirect('dashboard:dishes')


@staff_member_required
@require_POST
def dish_toggle(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    dish.is_available = not dish.is_available
    dish.save(update_fields=['is_available'])
    messages.info(request, f'{dish.name} is now {"AVAILABLE" if dish.is_available else "SOLD OUT"}.')
    return redirect(request.POST.get('next') or 'dashboard:dishes')


@staff_member_required
def categories_list(request):
    categories = Category.objects.annotate(dish_count=Count('dishes'))
    return render(request, 'dashboard/categories.html', {'categories': categories})


@staff_member_required
def category_form(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, request.FILES or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Category {"updated" if category else "created"} ✅')
        return redirect('dashboard:categories')
    return render(request, 'dashboard/form.html', {
        'form': form,
        'title': f'Edit {category.name}' if category else 'New category',
        'back_url': 'dashboard:categories',
    })


@staff_member_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.dishes.exists():
        messages.error(request, f'"{category.name}" still has dishes — move or delete them first.')
    else:
        category.delete()
        messages.success(request, 'Category deleted.')
    return redirect('dashboard:categories')


@staff_member_required
def coupons_list(request):
    return render(request, 'dashboard/coupons.html', {
        'coupons': Coupon.objects.order_by('-created_at'),
        'now': timezone.now(),
    })


@staff_member_required
def coupon_form(request, pk=None):
    coupon = get_object_or_404(Coupon, pk=pk) if pk else None
    form = CouponForm(request.POST or None, instance=coupon)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Coupon {"updated" if coupon else "created"} ✅')
        return redirect('dashboard:coupons')
    return render(request, 'dashboard/form.html', {
        'form': form,
        'title': f'Edit {coupon.code}' if coupon else 'New coupon',
        'back_url': 'dashboard:coupons',
    })


@staff_member_required
@require_POST
def coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.delete()
    messages.success(request, 'Coupon deleted.')
    return redirect('dashboard:coupons')


# ---------- users ----------

@staff_member_required
def users_list(request):
    qs = User.objects.annotate(order_count=Count('orders')).order_by('username')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
    role = request.GET.get('role', '')
    if role in dict(User.ROLE_CHOICES):
        qs = qs.filter(role=role)
    page = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'dashboard/users.html', {
        'page_obj': page, 'q': q, 'cur_role': role,
        'role_choices': User.ROLE_CHOICES,
    })


@staff_member_required
@require_POST
def user_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    role = request.POST.get('role')
    if role in dict(User.ROLE_CHOICES) and not (user == request.user and role != user.role):
        user.role = role
    if 'is_active' in request.POST:
        if user == request.user:
            messages.error(request, 'You cannot deactivate your own account.')
        else:
            user.is_active = True
    elif user != request.user:
        user.is_active = False
    user.save()
    messages.success(request, f'{user.username} updated.')
    return redirect('dashboard:users')


# ---------- reviews ----------

@staff_member_required
def reviews_list(request):
    qs = Review.objects.select_related('user', 'dish', 'restaurant')
    f = request.GET.get('filter', '')
    if f == 'reported':
        qs = qs.filter(reported=True)
    elif f == 'unapproved':
        qs = qs.filter(is_approved=False)
    return render(request, 'dashboard/reviews.html', {
        'reviews': qs[:100], 'cur_filter': f,
    })


@staff_member_required
@require_POST
def review_moderate(request, pk):
    review = get_object_or_404(Review, pk=pk)
    action = request.POST.get('action')
    if action == 'toggle':
        review.is_approved = not review.is_approved
        review.reported = False
        review.save(update_fields=['is_approved', 'reported'])
        messages.info(request, f'Review {"approved" if review.is_approved else "hidden"}.')
    elif action == 'delete':
        review.delete()
        messages.success(request, 'Review deleted.')
    return redirect('dashboard:reviews')


# ============================================================
# RESTAURANT OWNER PANEL
# ============================================================

def _owner_restaurant(user):
    restaurant = user.owned_restaurants.first()
    if restaurant is None:
        raise Http404('No restaurant is linked to your account.')
    return restaurant


def panel_required(view):
    """Owner-panel guard: logged in + linked to a restaurant."""
    from functools import wraps

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import resolve_url
            return redirect(f'{resolve_url(settings.LOGIN_URL)}?next={request.path}')
        if not request.user.is_owner:
            messages.error(request, 'The owner panel is for restaurant partners only.')
            return redirect('core:home')
        return view(request, *args, **kwargs)
    return wrapper


@panel_required
def panel_home(request):
    restaurant = _owner_restaurant(request.user)
    items_qs = OrderItem.objects.filter(dish__restaurant=restaurant)
    orders_qs = Order.objects.filter(items__in=items_qs).distinct()

    # monthly earnings for the last 6 months
    today = timezone.localdate()
    month = today.replace(day=1)
    months = []
    for _ in range(6):
        months.append(month)
        month = (month - timedelta(days=1)).replace(day=1)
    months.reverse()
    earnings = []
    for m in months:
        nxt = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        rev = (items_qs.filter(order__status=Order.Status.DELIVERED,
                               order__created_at__date__gte=m,
                               order__created_at__date__lt=nxt)
               .aggregate(s=Sum(F('price') * F('quantity')))['s'] or 0)
        earnings.append({'month': m.strftime('%b %Y'), 'amount': float(rev)})

    return render(request, 'panel/home.html', {
        'restaurant': restaurant,
        'orders_total': orders_qs.count(),
        'orders_pending': orders_qs.filter(status__in=[Order.Status.PENDING,
                                                       Order.Status.CONFIRMED,
                                                       Order.Status.PREPARING]).count(),
        'revenue_total': (items_qs.filter(order__status=Order.Status.DELIVERED)
                          .aggregate(s=Sum(F('price') * F('quantity')))['s'] or 0),
        'dishes_total': restaurant.dishes.count(),
        'dishes_available': restaurant.dishes.filter(is_available=True).count(),
        'earnings': earnings,
        'recent_orders': orders_qs.select_related('user')[:8],
    })


@panel_required
def panel_orders(request):
    restaurant = _owner_restaurant(request.user)
    qs = (Order.objects.filter(items__dish__restaurant=restaurant)
          .distinct().select_related('user', 'address'))
    status = request.GET.get('status', '')
    if status in Order.Status.values:
        qs = qs.filter(status=status)
    page = Paginator(qs, 12).get_page(request.GET.get('page'))
    return render(request, 'panel/orders.html', {
        'restaurant': restaurant, 'page_obj': page,
        'status_choices': Order.Status.choices, 'current_status': status,
    })


@panel_required
def panel_dishes(request):
    restaurant = _owner_restaurant(request.user)
    dishes = restaurant.dishes.select_related('category').order_by('category__name', 'name')
    return render(request, 'panel/dishes.html', {
        'restaurant': restaurant, 'dishes': dishes,
    })


@panel_required
@require_POST
def panel_dish_update(request, pk):
    """Owner quick-actions: toggle availability or tweak prices."""
    restaurant = _owner_restaurant(request.user)
    dish = get_object_or_404(Dish, pk=pk, restaurant=restaurant)

    if 'toggle' in request.POST:
        dish.is_available = not dish.is_available
        dish.save(update_fields=['is_available'])
        messages.info(request, f'{dish.name}: {"available" if dish.is_available else "sold out"}.')
    else:
        try:
            dish.price = max(0, float(request.POST.get('price', dish.price)))
            raw = request.POST.get('discount_price', '').strip()
            dish.discount_price = float(raw) if raw else None
            dish.save(update_fields=['price', 'discount_price'])
            messages.success(request, f'{dish.name} prices saved ✅')
        except ValueError:
            messages.error(request, 'Prices must be numbers.')
    return redirect('panel:dishes')
