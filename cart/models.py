from django.conf import settings
from django.db import models


class Cart(models.Model):
    """Persistent cart for a logged-in user (guests use a session cart)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Cart of {self.user.username} ({self.items.count()} items)'

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """One dish + quantity inside a cart."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    dish = models.ForeignKey('core.Dish', on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'dish')
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.quantity} × {self.dish.name}'

    @property
    def sub_total(self):
        return self.dish.effective_price * self.quantity


class Wishlist(models.Model):
    """A dish a user saved for later (heart icon)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_items')
    dish = models.ForeignKey('core.Dish', on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'dish')
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.user.username} ♥ {self.dish.name}'
