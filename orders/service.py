"""Order placement + notification helpers."""
from decimal import Decimal

from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string

from cart import service as cart_service
from core.models import Coupon
from .models import Order, OrderItem


class CheckoutError(Exception):
    """Raised with a customer-friendly message when an order can't be placed."""


@transaction.atomic
def place_order(request, address, payment_method, instructions=''):
    """Turn the current cart into an Order. Returns the Order.

    Re-validates everything server-side (cart, address ownership, payment
    method, coupon) — never trusts the checkout form.
    """
    if request.user != address.user:
        raise CheckoutError('That address does not belong to your account.')

    if payment_method not in Order.LIVE_PAYMENT_METHODS:
        raise CheckoutError('Please choose Cash on Delivery — other payment methods are coming soon.')

    lines, totals = cart_service.get_lines(request)
    if not lines:
        raise CheckoutError('Your cart is empty — add some delicious food first! 🍕')

    # re-validate the applied coupon at order time (it may have expired /
    # hit its usage limit / the cart may have shrunk below the minimum)
    coupon = totals.get('coupon')
    if coupon is None and totals.get('coupon_error') and request.session.get(
            cart_service.COUPON_SESSION_KEY):
        # a coupon is stored but no longer usable — never silently drop the
        # discount the customer was counting on; make them review first
        cart_service.remove_coupon(request)
        raise CheckoutError(
            f'{totals["coupon_error"]} Your coupon was removed — please review '
            'the summary and place the order again.')
    if coupon:
        fresh = Coupon.objects.filter(code=coupon.code).first()
        if fresh is None or not fresh.is_valid_now:
            cart_service.remove_coupon(request)
            raise CheckoutError('Your coupon is no longer valid and was removed. Please review the summary and try again.')
        if totals['subtotal'] < fresh.min_order_amount:
            raise CheckoutError(
                f'Your cart dropped below the ₹{fresh.min_order_amount:g} minimum for {fresh.code}.')
        coupon = fresh

    order = Order.objects.create(
        user=request.user,
        address=address,
        address_snapshot=address.single_line,
        payment_method=payment_method,
        subtotal=totals['subtotal'],
        delivery_fee=totals['delivery'],
        tax=totals['tax'],
        discount=totals['discount'],
        total=totals['total'],
        coupon_code=coupon.code if coupon else '',
        special_instructions=(instructions or '')[:500],
        eta_minutes=totals['eta'] or 40,
    )

    for line in lines:
        dish = line['dish']
        OrderItem.objects.create(
            order=order,
            dish=dish,
            dish_name=dish.name,
            dish_image=dish.image.name if dish.image else '',
            quantity=line['quantity'],
            price=dish.effective_price,
        )

    if coupon:
        coupon.used_count += 1
        coupon.save(update_fields=['used_count'])

    # the cart's job is done
    cart_service.clear(request)
    cart_service.remove_coupon(request)

    send_order_confirmation_email(order)
    return order


def send_order_confirmation_email(order):
    """Order confirmation — best-effort (never blocks checkout)."""
    if not order.user.email:
        return
    try:
        body = render_to_string('orders/order_confirmation_email.txt', {'order': order})
        send_mail(
            subject=f'QuickBite order {order.order_id} confirmed! 🍔',
            message=body,
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[order.user.email],
            fail_silently=True,
        )
    except Exception:
        pass

def send_status_update_email(order):
    """Status-change notification — best-effort."""
    if not order.user.email:
        return
    try:
        send_mail(
            subject=f'QuickBite order {order.order_id}: {order.get_status_display()}',
            message=(
                f'Hi {order.user.display_name},\n\n'
                f'Your order {order.order_id} is now: {order.get_status_display().upper()}.\n'
                f'Track it anytime: {order.get_absolute_url()}\n\n'
                f'— Team QuickBite 🍔'
            ),
            from_email=None,
            recipient_list=[order.user.email],
            fail_silently=True,
        )
    except Exception:
        pass
