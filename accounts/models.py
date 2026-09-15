from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """QuickBite user — Django's AbstractUser + delivery profile fields."""

    phone_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('owner', 'Restaurant Owner'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

    class Meta:
        ordering = ['username']

    def __str__(self):
        return self.email or self.username

    @property
    def is_owner(self):
        return self.role == 'owner' or self.owned_restaurants.exists()

    @property
    def display_name(self):
        """Full name if set, else username (used across templates)."""
        return self.get_full_name() or self.username

    @property
    def initials(self):
        """Up-to-two initials for the avatar fallback."""
        parts = self.get_full_name().split() or [self.username]
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.username[:2].upper()

    @property
    def profile_complete(self):
        """Rough completion meter for the profile page."""
        fields = [self.first_name, self.last_name, self.email, self.phone_number,
                  self.address, self.city, self.pincode, self.date_of_birth,
                  self.profile_picture]
        filled = sum(1 for f in fields if f)
        return int(filled / len(fields) * 100)
