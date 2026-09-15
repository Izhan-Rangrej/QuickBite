from django.conf import settings
from django.db import models


class Review(models.Model):
    """Customer review for a dish or a restaurant (one of the two).

    Reviews created through the post-delivery form on the order page carry
    an `order` reference and render with a "Verified Order" badge.
    """

    RATING_CHOICES = [(i, f'{i} star{"s" if i > 1 else ""}') for i in range(5, 0, -1)]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    dish = models.ForeignKey(
        'core.Dish', on_delete=models.CASCADE, null=True, blank=True,
        related_name='reviews')
    restaurant = models.ForeignKey(
        'core.Restaurant', on_delete=models.CASCADE, null=True, blank=True,
        related_name='reviews')
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviews')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(max_length=1000, blank=True)
    is_approved = models.BooleanField(default=True)
    reported = models.BooleanField(default=False, help_text='Flagged by a customer')
    helpful_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='helpful_reviews')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'dish'), name='one_review_per_user_per_dish'),
            models.UniqueConstraint(
                fields=('user', 'restaurant'), name='one_review_per_user_per_restaurant'),
        ]

    def __str__(self):
        target = self.dish or self.restaurant
        return f'{self.rating}★ by {self.user} on {target}'

    @property
    def target(self):
        return self.dish or self.restaurant

    @property
    def is_verified(self):
        return self.order_id is not None

    @property
    def helpful_count(self):
        return self.helpful_users.count()


def avg_rating(queryset):
    """(average, count) of approved reviews for a dish/restaurant queryset."""
    from django.db.models import Avg
    agg = queryset.filter(is_approved=True).aggregate(a=Avg('rating'), n=models.Count('id'))
    return (round(agg['a'], 1) if agg['a'] else None), agg['n']
