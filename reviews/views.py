from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.models import Dish, Restaurant
from orders.models import Order

from .models import Review


@login_required
@require_POST
def add_review(request):
    """Create a dish or restaurant review.

    From the order page the POST carries `order_id`; we verify the order is
    delivered and actually contains the dish — those reviews get the
    "Verified Order" badge.
    """
    target_type = request.POST.get('target_type')
    target_id = request.POST.get('target_id')
    try:
        rating = int(request.POST.get('rating', 0))
    except (TypeError, ValueError):
        rating = 0
    comment = (request.POST.get('comment') or '').strip()[:1000]

    back = request.POST.get('next') or '/'

    if rating < 1 or rating > 5:
        messages.error(request, 'Please pick a star rating between 1 and 5.')
        return redirect(back)

    order = None
    if target_type == 'dish':
        target = get_object_or_404(Dish, pk=target_id)
        order_id = request.POST.get('order_id')
        if not order_id:
            messages.error(request, 'Dish reviews open once your order is delivered. 🍽️')
            return redirect(back)
        order = get_object_or_404(Order, order_id=order_id, user=request.user)
        if order.status != Order.Status.DELIVERED:
            messages.error(request, 'You can review an order once it is delivered.')
            return redirect(back)
        if not order.items.filter(dish=target).exists():
            messages.error(request, 'That dish was not part of this order.')
            return redirect(back)
    elif target_type == 'restaurant':
        target = get_object_or_404(Restaurant, pk=target_id)
    else:
        messages.error(request, 'Unknown review target.')
        return redirect(back)

    exists = Review.objects.filter(
        user=request.user,
        dish=target if target_type == 'dish' else None,
        restaurant=target if target_type == 'restaurant' else None,
    ).exists()
    if exists:
        messages.info(request, 'You have already reviewed this — thanks!')
        return redirect(back)

    Review.objects.create(
        user=request.user,
        dish=target if target_type == 'dish' else None,
        restaurant=target if target_type == 'restaurant' else None,
        order=order,
        rating=rating,
        comment=comment,
    )
    messages.success(request, f'Thanks for the {rating}★ review! 🌟')
    return redirect(back)


@login_required
@require_POST
def toggle_helpful(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if review.helpful_users.filter(pk=request.user.pk).exists():
        review.helpful_users.remove(request.user)
        active = False
    else:
        review.helpful_users.add(request.user)
        active = True
    return JsonResponse({'ok': True, 'active': active,
                         'helpful_count': review.helpful_count})


@login_required
@require_POST
def report_review(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.reported = True
    review.save(update_fields=['reported'])
    return JsonResponse({'ok': True, 'message': 'Reported — our team will take a look.'})
