from django.conf import settings
from django.contrib import admin
from django.urls import include, path

# Custom error pages (Phase 10)
from core.error_views import bad_request, page_not_found, permission_denied, server_error
from core.ops import healthz, serve_media

handler400 = 'core.error_views.bad_request'
handler403 = 'core.error_views.permission_denied'
handler404 = 'core.error_views.page_not_found'
handler500 = 'core.error_views.server_error'

urlpatterns = [
    # Render health check (see core/ops.py) — kept out of sitemaps and robots.
    path('healthz', healthz, name='healthz'),
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

# Uploaded media (dish/restaurant photos). Served by our own view in *both* modes:
# production has no other server for /media/ (WhiteNoise only handles staticfiles/),
# and sharing one implementation keeps dev and prod identical. The view restricts
# media/ to image types — an uploaded .html or .svg served inline from the site's own
# origin would be stored XSS — refuses traversal out of MEDIA_ROOT, and sets caching.
urlpatterns.append(
    path(f'{settings.MEDIA_URL.lstrip("/")}<path:path>', serve_media, name='media')
)
