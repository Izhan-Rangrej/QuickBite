from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    # checkout
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/success/<str:order_id>/', views.order_success, name='order_success'),

    # address management (from checkout)
    path('checkout/address/add/', views.address_add, name='address_add'),
    path('checkout/address/<int:pk>/edit/', views.address_edit, name='address_edit'),
    path('checkout/address/<int:pk>/delete/', views.address_delete, name='address_delete'),
    path('checkout/address/<int:pk>/default/', views.address_set_default, name='address_set_default'),

    # orders
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<str:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<str:order_id>/invoice/', views.order_invoice, name='order_invoice'),
    path('orders/<str:order_id>/cancel/', views.order_cancel, name='order_cancel'),
    path('orders/<str:order_id>/reorder/', views.order_reorder, name='order_reorder'),
]
