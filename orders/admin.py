from django.contrib import admin

from .models import Address, Order, OrderItem
from .service import send_status_update_email


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'city', 'pincode',
                    'address_type', 'is_default', 'created_at')
    list_filter = ('address_type', 'is_default', 'city')
    search_fields = ('full_name', 'phone', 'city', 'user__username')
    autocomplete_fields = ('user',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('dish', 'dish_name', 'quantity', 'price', 'sub_total')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # order contents are immutable history


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'status_badge', 'total',
                    'payment_method', 'item_count', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('order_id', 'user__username', 'user__email')
    autocomplete_fields = ('user',)
    readonly_fields = ('order_id', 'address_snapshot', 'subtotal', 'delivery_fee',
                       'tax', 'discount', 'total', 'coupon_code',
                       'eta_minutes', 'created_at', 'updated_at', 'delivered_at')
    inlines = (OrderItemInline,)
    fieldsets = (
        ('Order', {'fields': ('order_id', 'user', 'status', 'created_at', 'updated_at')}),
        ('Delivery', {'fields': ('address', 'address_snapshot', 'eta_minutes', 'delivered_at')}),
        ('Payment & totals', {
            'fields': ('payment_method', 'subtotal', 'delivery_fee', 'tax',
                       'discount', 'total', 'coupon_code'),
        }),
        ('Notes', {'fields': ('special_instructions',)}),
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending': '#f57f17', 'confirmed': '#1565c0', 'preparing': '#e65100',
            'out_for_delivery': '#6a1b9a', 'delivered': '#2e7d32', 'cancelled': '#c62828',
        }
        from django.utils.html import format_html
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:20px;'
            'font-size:11px;font-weight:600;">{}</span>',
            colors.get(obj.status, '#666'), obj.get_status_display())

    @admin.display(description='Items')
    def item_count(self, obj):
        return obj.items.count()

    def save_model(self, request, obj, form, change):
        status_changed = change and 'status' in form.changed_data
        just_delivered = status_changed and obj.status == Order.Status.DELIVERED
        super().save_model(request, obj, form, change)
        if just_delivered and not obj.delivered_at:
            from django.utils import timezone
            obj.delivered_at = timezone.now()
            obj.save(update_fields=['delivered_at'])
        if status_changed:
            send_status_update_email(obj)
