from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [
    path('reviews/add/', views.add_review, name='add'),
    path('reviews/<int:pk>/helpful/', views.toggle_helpful, name='helpful'),
    path('reviews/<int:pk>/report/', views.report_review, name='report'),
]
