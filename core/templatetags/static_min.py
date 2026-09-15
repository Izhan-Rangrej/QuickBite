"""{% static_min %} — serves `static/dist/...` minified copies in production.

`python manage.py minify_static` (rcssmin / rjsmin) builds the dist copies.
In DEBUG the originals are served so debugging stays pleasant.
"""
from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

_MINIFIABLE = ('.css', '.js')


@register.simple_tag
def static_min(path):
    if not settings.DEBUG and path.endswith(_MINIFIABLE) and '.min.' not in path:
        return static(f'dist/{path}')
    return static(path)
