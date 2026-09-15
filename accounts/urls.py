from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),

    path('password/change/', views.QuickBitePasswordChangeView.as_view(),
         name='password_change'),

    path('password/reset/', views.QuickBitePasswordResetView.as_view(),
         name='password_reset'),
    path('password/reset/done/', views.QuickBitePasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/',
         views.QuickBitePasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('password/reset/complete/',
         views.QuickBitePasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
]
