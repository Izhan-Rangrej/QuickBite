from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from cart import service as cart_service
from .forms import AddressForm
from .models import Order
from .service import CheckoutError, place_order, send_status_update_email


# ---------- checkout ----------

@login_required
def checkout(request):
    """3-step checkout: address → payment → review & place order."""
    lines, totals = cart_service.get_lines(request)
    addresses = request.user.addresses.all()
    form = AddressForm()
    # the "add address" inputs live outside <form id="checkoutForm"> — wire
    # them to their own standalone form via the HTML5 form= attribute
    for field in form.fields.values():
        field.widget.attrs['form'] = 'addressAddForm'

    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        payment = request.POST.get('payment_method', 'cod')
        instructions = request.POST.get('instructions', '')

        address = None
        if address_id == 'new':
            form = AddressForm(request.POST)
            if form.is_valid():
                address = form.save(commit=False)
                address.user = request.user
                address.save()
                messages.success(request, 'Address saved! ✅')
            else:
                messages.error(request, 'Please fix the errors in the new address form.')
                return render(request, 'orders/checkout.html', {
                    'lines': lines, 'totals': totals, 'addresses': addresses,
                    'form': form, 'show_address_form': True,
                    'selected_address_id': 'new', 'selected_payment': payment,
                })
        else:
            address = request.user.addresses.filter(pk=address_id).first()
            if address is None:
                messages.error(request, 'Please choose a delivery address.')
                return redirect('orders:checkout')

        try:
            order = place_order(request, address, payment, instructions)
        except CheckoutError as exc:
            messages.error(request, str(exc))
            return redirect('orders:checkout')

        return redirect('orders:order_success', order_id=order.order_id)

    # ?select=<pk> — used after adding/editing an address (redirect back here)
    selected = None
    select = request.GET.get('select')
    if select:
        selected = addresses.filter(pk=select).first()
    if selected is None:
        selected = addresses.filter(is_default=True).first() or addresses.first()
    return render(request, 'orders/checkout.html', {
        'lines': lines, 'totals': totals, 'addresses': addresses, 'form': form,
        'selected_address_id': selected.pk if selected else None,
        'selected_payment': 'cod',
    })


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'orders/order_success.html', {'order': order})


# ---------- address CRUD (checkout widgets) ----------

def _back_to_checkout(request):
    return redirect(request.POST.get('next') or 'orders:checkout')


@login_required
def address_add(request):
    if request.method != 'POST':
        return redirect('orders:checkout')
    form = AddressForm(request.POST)
    if form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, 'Address added! ✅')
        return redirect(f"/checkout/?select={address.pk}")
    messages.error(request, 'Could not save the address — please check the form.')
    return _back_to_checkout(request)


@login_required
def address_edit(request, pk):
    address = get_object_or_404(request.user.addresses, pk=pk)
    if request.method != 'POST':
        return redirect('orders:checkout')
    form = AddressForm(request.POST, instance=address)
    if form.is_valid():
        form.save()
        messages.success(request, 'Address updated! ✅')
    else:
        messages.error(request, 'Could not update the address — please check the form.')
    return _back_to_checkout(request)


@login_required
def address_delete(request, pk):
    address = get_object_or_404(request.user.addresses, pk=pk)
    if request.method == 'POST':
        was_default = address.is_default
        address.delete()
        # promote another address to default if we removed it
        if was_default:
            nxt = request.user.addresses.first()
            if nxt:
                nxt.is_default = True
                nxt.save()
        messages.info(request, 'Address removed.')
    return _back_to_checkout(request)


@login_required
def address_set_default(request, pk):
    address = get_object_or_404(request.user.addresses, pk=pk)
    if request.method == 'POST':
        address.is_default = True
        address.save()  # save() unsets the others
        messages.success(request, f'{address.get_address_type_display()} address set as default.')
    return _back_to_checkout(request)


# ---------- my orders ----------

@login_required
def my_orders(request):
    qs = request.user.orders.select_related('address')

    status = request.GET.get('status', '')
    if status in Order.Status.values:
        qs = qs.filter(status=status)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(order_id__icontains=q))

    return render(request, 'orders/my_orders.html', {
        'orders': qs,
        'status_choices': Order.Status.choices,
        'current_status': status,
        'q': q,
        'orders_count': request.user.orders.count(),
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('address').prefetch_related('items'),
        order_id=order_id, user=request.user)

    # Phase 9: delivered orders unlock per-dish reviews (skip already-reviewed)
    reviewed = set()
    if order.status == Order.Status.DELIVERED:
        from reviews.models import Review
        reviewed = set(Review.objects.filter(
            user=request.user, order=order).values_list('dish_id', flat=True))
        reviewed |= set(Review.objects.filter(
            user=request.user,
            dish_id__in=[i.dish_id for i in order.items.all() if i.dish_id],
        ).values_list('dish_id', flat=True))

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'reviewed_dish_ids': reviewed,
    })


@login_required
def order_invoice(request, order_id):
    """Plain-text invoice download (no PDF dependency)."""
    order = get_object_or_404(
        Order.objects.prefetch_related('items'), order_id=order_id, user=request.user)

    w = 56
    lines = [
        '=' * w,
        'QUICKBITE — TAX INVOICE'.center(w),
        '=' * w,
        f'Order ID     : {order.order_id}',
        f'Placed on    : {order.created_at:%d %b %Y, %I:%M %p}',
        f'Status       : {order.get_status_display()}',
        f'Payment      : {order.payment_display}',
        '',
        'DELIVER TO',
        f'  {order.address.full_name} ({order.address.phone})',
        f'  {order.address_snapshot}',
        '',
        '-' * w,
        f'{"ITEM":<34}{"QTY":>5}{"AMOUNT":>17}',
        '-' * w,
    ]
    for item in order.items.all():
        name = item.dish_name[:32]
        lines.append(f'{name:<34}{item.quantity:>5}{("Rs " + format(item.sub_total, ",.2f")):>17}')
    lines += [
        '-' * w,
        f'{"Subtotal":<49}{("Rs " + format(order.subtotal, ",.2f")):>7}',
        f'{"Delivery fee":<49}{("Rs " + format(order.delivery_fee, ",.2f")):>7}',
        f'{"GST (5%)":<49}{("Rs " + format(order.tax, ",.2f")):>7}',
    ]
    if order.discount:
        lines.append(f'{("Coupon " + order.coupon_code):<49}{("- Rs " + format(order.discount, ",.2f")):>7}')
    lines += [
        '=' * w,
        f'{"TOTAL PAID":<49}{("Rs " + format(order.total, ",.2f")):>7}',
        '=' * w,
        '',
        'Thank you for ordering with QuickBite! 🍔',
        'Questions? hello@quickbite.com · +91 98765 43210',
    ]
    response = HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="QuickBite-Invoice-{order.order_id}.txt"'
    return response


@login_required
def order_cancel(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if request.method == 'POST':
        if not order.can_cancel:
            messages.error(request, f'An order that is "{order.get_status_display()}" can no longer be cancelled.')
        else:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status', 'updated_at'])
            send_status_update_email(order)
            messages.success(request, f'Order {order.order_id} cancelled. Any refund is on its way.')
    return redirect('orders:order_detail', order_id=order.order_id)


@login_required
def order_reorder(request, order_id):
    """Push every still-available item of a past order back into the cart."""
    order = get_object_or_404(
        Order.objects.prefetch_related('items__dish'), order_id=order_id, user=request.user)
    if request.method != 'POST':
        return redirect('orders:order_detail', order_id=order.order_id)

    added, skipped = 0, 0
    for item in order.items.all():
        dish = item.dish
        if dish and dish.is_available and dish.restaurant.is_active:
            cart_service.add_item(request, dish, item.quantity)
            added += 1
        else:
            skipped += 1

    if added:
        messages.success(request, f'{added} item{"s" if added > 1 else ""} added back to your cart! 🛒')
    if skipped:
        messages.warning(request, f'{skipped} item{"s were" if skipped > 1 else " was"} unavailable and skipped.')
    if not added and not skipped:
        messages.info(request, 'Nothing could be re-added from this order.')
    return redirect('cart:cart_page')
