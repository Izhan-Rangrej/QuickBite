from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'rating', 'is_approved', 'reported', 'created_at')
    list_filter = ('is_approved', 'reported', 'rating', 'created_at')
    search_fields = ('comment', 'user__username', 'dish__name', 'restaurant__name')
    list_editable = ('is_approved',)
    date_hierarchy = 'created_at'
