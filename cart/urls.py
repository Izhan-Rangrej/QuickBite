from django.urls import path

from . import views

app_name = 'cart'

urlpatterns = [
    # pages
    path('cart/', views.cart_page, name='cart_page'),
    path('wishlist/', views.wishlist_page, name='wishlist_page'),

    # cart AJAX (JSON)
    path('cart/add/', views.cart_add, name='cart_add'),
    path('cart/update/', views.cart_update, name='cart_update'),
    path('cart/remove/', views.cart_remove, name='cart_remove'),
    path('cart/coupon/apply/', views.coupon_apply, name='coupon_apply'),
    path('cart/coupon/remove/', views.coupon_remove, name='coupon_remove'),

    # wishlist AJAX (JSON)
    path('wishlist/toggle/', views.wishlist_toggle, name='wishlist_toggle'),
]
