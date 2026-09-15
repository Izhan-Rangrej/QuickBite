from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class QuickBiteUserAdmin(UserAdmin):
    """Default UserAdmin + the QuickBite delivery-profile fields."""

    list_display = ('username', 'email', 'first_name', 'last_name',
                    'phone_number', 'city', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'phone_number', 'city')
    list_filter = ('is_staff', 'is_active', 'city')

    fieldsets = UserAdmin.fieldsets + (
        ('Delivery profile', {
            'fields': ('phone_number', 'address', 'city', 'pincode',
                       'profile_picture', 'date_of_birth'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Delivery profile', {
            'fields': ('email', 'phone_number'),
        }),
    )
