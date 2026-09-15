"""Template globals — delivery-location chip + site-wide SEO defaults."""

from django.conf import settings

LOCATION_SESSION_KEYS = ('delivery_lat', 'delivery_lon', 'delivery_label')


def delivery_location(request):
    lat = request.session.get('delivery_lat')
    lon = request.session.get('delivery_lon')
    label = request.session.get('delivery_label')
    return {
        'delivery_lat': lat,
        'delivery_lon': lon,
        'delivery_label': label,
        'has_location': lat is not None and lon is not None,
    }


def seo_defaults(request):
    """Site-wide meta/OG defaults + analytics ids (overridable per page via blocks)."""
    return {
        'site_name': settings.SITE_NAME,
        'site_tagline': settings.SITE_TAGLINE,
        'site_url': settings.SITE_URL.rstrip('/'),
        'ga_measurement_id': settings.GA_MEASUREMENT_ID,
        'search_console_token': settings.SEARCH_CONSOLE_TOKEN,
    }
