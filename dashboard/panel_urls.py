from django.urls import path

from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.panel_home, name='home'),
    path('orders/', views.panel_orders, name='orders'),
    path('dishes/', views.panel_dishes, name='dishes'),
    path('dishes/<int:pk>/update/', views.panel_dish_update, name='dish_update'),
]
