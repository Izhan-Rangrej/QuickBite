import random
import string
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Address(models.Model):
    """A saved delivery address for a user."""

    class AddressType(models.TextChoices):
        HOME = 'home', '🏠 Home'
        WORK = 'work', '🏢 Work'
        OTHER = 'other', '📍 Other'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, default='Gujarat')
    pincode = models.CharField(max_length=6)
    address_type = models.CharField(
        max_length=10, choices=AddressType.choices, default=AddressType.HOME)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name_plural = 'Addresses'

    def __str__(self):
        return f'{self.full_name} — {self.city} ({self.get_address_type_display()})'

    def save(self, *args, **kwargs):
        # first address of a user becomes default automatically
        if not self.pk and not self.user.addresses.exists():
            self.is_default = True
        # only one default per user
        if self.is_default:
            self.user.addresses.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def single_line(self):
        parts = [self.address_line1, self.address_line2, self.landmark,
                 f'{self.city}, {self.state} {self.pincode}']
        return ', '.join(p for p in parts if p)


class Order(models.Model):
    """A placed order. Money values are snapshots — later price/coupon changes
    never rewrite history."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PREPARING = 'preparing', 'Preparing'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for Delivery'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    class PaymentMethod(models.TextChoices):
        COD = 'cod', 'Cash on Delivery'
        UPI = 'upi', 'UPI'
        CARD = 'card', 'Card'
        WALLET = 'wallet', 'Wallet'

    # statuses that can still be cancelled by the customer
    CANCELLABLE = [Status.PENDING, Status.CONFIRMED]
    # happy-path order for the tracking timeline
    TRACK_STEPS = [Status.PENDING, Status.CONFIRMED, Status.PREPARING,
                   Status.OUT_FOR_DELIVERY, Status.DELIVERED]
    # payment methods that actually work right now
    LIVE_PAYMENT_METHODS = [PaymentMethod.COD]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    order_id = models.CharField(max_length=20, unique=True, editable=False, blank=True)

    address = models.ForeignKey(
        Address, on_delete=models.PROTECT, related_name='orders')
    address_snapshot = models.TextField(editable=False)

    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING)

    # money snapshots
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2)

    coupon_code = models.CharField(max_length=30, blank=True)
    special_instructions = models.TextField(blank=True, max_length=500)

    eta_minutes = models.PositiveIntegerField(default=40)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_id} — {self.user.username} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = self._generate_order_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_id():
        """QB<yymmdd>-<6 random chars>, collision-checked."""
        while True:
            stamp = timezone.localdate().strftime('%y%m%d')
            rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            candidate = f'QB{stamp}-{rand}'
            if not Order.objects.filter(order_id=candidate).exists():
                return candidate

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('orders:order_detail', args=[self.order_id])

    @property
    def can_cancel(self):
        return self.status in self.CANCELLABLE

    @property
    def timeline_steps(self):
        """[(status, label, state)] for the tracking timeline.
        state is one of: done | current | upcoming."""
        if self.status == self.Status.CANCELLED:
            return []
        current_idx = self.TRACK_STEPS.index(self.status)
        return [
            (s, Order.Status(s).label,
             'done' if i < current_idx else 'current' if i == current_idx else 'upcoming')
            for i, s in enumerate(self.TRACK_STEPS)
        ]

    @property
    def payment_display(self):
        if self.payment_method == self.PaymentMethod.COD:
            return 'Cash on Delivery'
        return self.get_payment_method_display()


class OrderItem(models.Model):
    """A line inside an order. Dish fields are snapshots so order history
    survives dish edits/deletion (dish itself is SET_NULL)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    dish = models.ForeignKey(
        'core.Dish', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='order_items')
    dish_name = models.CharField(max_length=150)
    dish_image = models.CharField(max_length=200, blank=True)  # media path at order time
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)  # unit price at order time

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.quantity} × {self.dish_name}'

    @property
    def sub_total(self):
        return self.price * self.quantity

    @property
    def image_url(self):
        """Public URL of the snapshotted dish image (empty if none)."""
        if not self.dish_image:
            return ''
        from django.conf import settings as django_settings
        return f'{django_settings.MEDIA_URL}{self.dish_image}'
