from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# Custom error pages (Phase 10)
from core.error_views import bad_request, page_not_found, permission_denied, server_error

handler400 = 'core.error_views.bad_request'
handler403 = 'core.error_views.permission_denied'
handler404 = 'core.error_views.page_not_found'
handler500 = 'core.error_views.server_error'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),  # auth: signup/login/profile/password
    path('', include('cart.urls')),   # cart + wishlist (pages & AJAX)
    path('', include('orders.urls')), # checkout & orders (must precede core)
    path('', include('reviews.urls')),  # reviews & ratings (pages & AJAX)
    path('dashboard/', include('dashboard.urls')),  # staff control panel
    path('panel/', include('dashboard.panel_urls')),  # restaurant owner panel
    path('', include('core.urls')),   # QuickBite landing page & core routes
]

if settings.DEBUG_TOOLBAR:
    urlpatterns.append(path('__debug__/', include('debug_toolbar.urls')))

# Serve user-uploaded media (food photos, etc.) during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
