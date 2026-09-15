from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Coupon, Dish, Restaurant

# ---- Brand the admin panel ----
admin.site.site_header = 'QuickBite Administration'
admin.site.site_title = 'QuickBite Admin'
admin.site.index_title = 'Manage your food delivery business'


def _thumb(obj, size=48):
    """Small rounded image preview for list pages."""
    if obj.image:
        return format_html(
            '<img src="{}" style="height:{}px;width:{}px;object-fit:cover;'
            'border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,.15);">',
            obj.image.url, size, size,
        )
    return format_html('<span style="color:#bbb;">— no image —</span>')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'preview', 'slug', 'dish_count', 'is_active')
    list_display_links = ('name', 'preview')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    fields = ('name', 'slug', 'image', 'description', 'is_active')

    @admin.display(description='Image')
    def preview(self, obj):
        return _thumb(obj, 40)

    @admin.display(description='Dishes')
    def dish_count(self, obj):
        return obj.dishes.count()


class DishInline(admin.TabularInline):
    """Manage a restaurant's dishes directly on its admin page."""
    model = Dish
    extra = 1
    fields = ('name', 'category', 'price', 'discount_price', 'rating',
              'is_bestseller', 'is_new', 'is_veg', 'is_available')
    autocomplete_fields = ('category',)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'preview', 'cuisine_type', 'rating', 'delivery_time',
                    'min_order', 'is_promoted', 'open_now', 'is_active')
    list_display_links = ('name', 'preview')
    list_editable = ('is_promoted', 'is_active')
    list_filter = ('cuisine_type', 'is_promoted', 'is_active')
    search_fields = ('name', 'description', 'address', 'phone')
    prepopulated_fields = {'slug': ('name',)}
    inlines = (DishInline,)
    fieldsets = (
        ('Basic info', {
            'fields': ('name', 'slug', 'image', 'description', 'cuisine_type'),
        }),
        ('Contact', {
            'fields': ('address', 'phone'),
        }),
        ('Operations', {
            'fields': ('rating', 'delivery_time', 'min_order',
                       'opening_time', 'closing_time'),
        }),
        ('Marketing & status', {
            'fields': ('offer_text', 'is_promoted', 'is_active'),
        }),
    )

    @admin.display(description='Image')
    def preview(self, obj):
        return _thumb(obj)

    @admin.display(description='Open now?', boolean=True)
    def open_now(self, obj):
        return obj.is_open_now


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'preview', 'restaurant', 'category', 'price',
                    'discount_price', 'off_percent', 'rating',
                    'is_bestseller', 'is_new', 'is_veg', 'is_available')
    list_display_links = ('name', 'preview')
    list_editable = ('is_bestseller', 'is_new', 'is_veg', 'is_available')
    list_filter = ('category', 'restaurant', 'is_veg', 'is_bestseller',
                   'is_new', 'is_available')
    search_fields = ('name', 'description', 'restaurant__name')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('restaurant', 'category')
    fieldsets = (
        ('Basic info', {
            'fields': ('name', 'slug', 'image', 'description'),
        }),
        ('Classification', {
            'fields': ('restaurant', 'category'),
        }),
        ('Pricing', {
            'fields': ('price', 'discount_price'),
        }),
        ('Badges & status', {
            'fields': ('rating', 'preparation_time',
                       'is_bestseller', 'is_new', 'is_veg', 'is_available'),
        }),
    )

    @admin.display(description='Image')
    def preview(self, obj):
        return _thumb(obj, 40)

    @admin.display(description='Off %', ordering='discount_price')
    def off_percent(self, obj):
        pct = obj.discount_percent
        return f'{pct}%' if pct else '—'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'discount_display', 'min_order_amount',
                    'max_discount', 'valid_from', 'valid_until',
                    'valid_now', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'valid_from', 'valid_until')
    search_fields = ('code', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Coupon', {
            'fields': ('code', 'title', 'description', 'is_active'),
        }),
        ('Discount (set ONE)', {
            'fields': ('discount_percentage', 'discount_amount',
                       'min_order_amount', 'max_discount'),
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until'),
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Discount')
    def discount_display(self, obj):
        return obj.discount_display

    @admin.display(description='Valid now?', boolean=True)
    def valid_now(self, obj):
        return obj.is_valid_now
