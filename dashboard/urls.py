from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),

    # orders
    path('orders/', views.orders_list, name='orders'),
    path('orders/<str:order_id>/', views.order_view, name='order_view'),
    path('orders/<str:order_id>/status/', views.order_status_update, name='order_status_update'),

    # restaurants
    path('restaurants/', views.restaurants_list, name='restaurants'),
    path('restaurants/new/', views.restaurant_form, name='restaurant_new'),
    path('restaurants/<int:pk>/edit/', views.restaurant_form, name='restaurant_edit'),
    path('restaurants/<int:pk>/delete/', views.restaurant_delete, name='restaurant_delete'),
    path('restaurants/<int:pk>/toggle/', views.restaurant_toggle, name='restaurant_toggle'),

    # dishes
    path('dishes/', views.dishes_list, name='dishes'),
    path('dishes/new/', views.dish_form, name='dish_new'),
    path('dishes/<int:pk>/edit/', views.dish_form, name='dish_edit'),
    path('dishes/<int:pk>/delete/', views.dish_delete, name='dish_delete'),
    path('dishes/<int:pk>/toggle/', views.dish_toggle, name='dish_toggle'),

    # categories
    path('categories/', views.categories_list, name='categories'),
    path('categories/new/', views.category_form, name='category_new'),
    path('categories/<int:pk>/edit/', views.category_form, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # users
    path('users/', views.users_list, name='users'),
    path('users/<int:pk>/update/', views.user_update, name='user_update'),

    # coupons
    path('coupons/', views.coupons_list, name='coupons'),
    path('coupons/new/', views.coupon_form, name='coupon_new'),
    path('coupons/<int:pk>/edit/', views.coupon_form, name='coupon_edit'),
    path('coupons/<int:pk>/delete/', views.coupon_delete, name='coupon_delete'),

    # reviews
    path('reviews/', views.reviews_list, name='reviews'),
    path('reviews/<int:pk>/moderate/', views.review_moderate, name='review_moderate'),
]
