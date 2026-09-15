from django.contrib import admin

from .models import Cart, CartItem, Wishlist


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ('dish',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_count', 'total_quantity', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    inlines = (CartItemInline,)

    @admin.display(description='Items')
    def item_count(self, obj):
        return obj.items.count()


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('dish', 'cart', 'quantity', 'sub_total', 'added_at')
    list_filter = ('dish__category',)
    search_fields = ('dish__name', 'cart__user__username')
    autocomplete_fields = ('cart', 'dish')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'dish', 'added_at')
    list_filter = ('dish__category',)
    search_fields = ('user__username', 'dish__name')
    autocomplete_fields = ('user', 'dish')
