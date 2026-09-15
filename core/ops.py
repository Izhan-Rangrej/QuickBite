"""Operational endpoints: health probe and production media serving.

These exist because of how the app is deployed (Render web service + Neon
Postgres, everything ephemeral except the database):

* ``healthz`` — a cheap path for Render's HTTP health check that does not render
  templates or require auth.
* ``serve_media`` — in production ``/media/`` (dish & restaurant photos, both the
  seeded ones and user uploads) has no server: Django only wires ``static()`` for
  media when ``DEBUG`` is on, and WhiteNoise is configured for ``staticfiles/``
  only. Without this route every uploaded image 404s the moment you deploy.
"""

import logging
import os
import posixpath
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from django.utils.http import http_date
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)

#: Only these extensions are ever served from MEDIA_ROOT. Anything else (an
#: uploaded .html / .svg / .xhtml) is a stored-XSS risk when served inline from
#: the same origin, so it is refused even if it somehow lands in media/.
MEDIA_EXTENSIONS = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.avif': 'image/avif',
}


@require_safe
def healthz(request):
    """Render health probe + a quick look at database connectivity.

    Always answers 200 while the process is up. A transient database error (Neon
    scales to zero after ~5 idle minutes, so the first query of the day can fail
    or be slow) must NOT make Render restart the instance in a loop — the app
    recovers on its own once the endpoint wakes up. The database result is reported
    in the body for humans instead.

    Add ``?db=1`` for a readiness-style answer: 503 when the DB is down.
    """
    db_ok, detail = True, ''
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception as exc:                       # noqa: BLE001 — probe must not raise
        db_ok = False
        first_line = (str(exc).strip().splitlines() or [''])[0]
        detail = f'{type(exc).__name__}: {first_line}'[:200]

    payload = {
        'status': 'ok' if db_ok else 'degraded',
        'database': 'ok' if db_ok else 'error',
        'vendor': connection.vendor,
        'time': timezone.now().isoformat(timespec='seconds'),
    }
    if not db_ok:
        payload['database_error'] = detail
        logger.warning('healthz: database check failed: %s', detail)

    status = 200
    if not db_ok and request.GET.get('db') in ('1', 'true', 'yes'):
        status = 503
    response = JsonResponse(payload, status=status)
    # Never cache a probe, and let Render's proxy treat it as-is.
    response['Cache-Control'] = 'no-store'
    return response


def _media_path(relative):
    """Resolve ``relative`` inside MEDIA_ROOT, refusing traversal. Returns a Path."""
    root = Path(settings.MEDIA_ROOT)
    rel = posixpath.normpath(str(relative).replace('\\', '/')).lstrip('/')
    if rel in ('', '.', '..') or '..' in Path(rel).parts:
        raise Http404('Invalid media path.')
    full = root / rel
    try:
        # realpath() both sides so symlinked mounts (a Render disk) still compare equal.
        root_r, full_r = os.path.realpath(root), os.path.realpath(full)
        if os.path.commonpath([root_r, full_r]) != root_r:
            raise Http404('Media path escapes MEDIA_ROOT.')
    except ValueError:        # different drives — never happens on Linux, be safe anyway
        raise Http404('Media path escapes MEDIA_ROOT.') from None
    return full


@require_safe
def serve_media(request, path):
    """Serve an uploaded file out of MEDIA_ROOT (production counterpart of DEBUG's
    ``static(settings.MEDIA_URL, ...)``), images only, with caching headers."""
    if not path.lower().endswith(tuple(MEDIA_EXTENSIONS)):
        raise Http404('Unsupported media type.')

    full = _media_path(path)
    if not full.is_file():
        raise Http404('File not found.')

    # The extension whitelist above means this lookup always hits; an image type is
    # also the only thing worth handing a browser from an upload directory.
    content_type = MEDIA_EXTENSIONS[full.suffix.lower()]

    stat = full.stat()
    response = FileResponse(full.open('rb'), content_type=content_type)
    response.headers['Last-Modified'] = http_date(stat.st_mtime)
    response.headers['Content-Length'] = str(stat.st_size)
    # Content-Disposition inline + nosniff (set globally) keeps uploads from ever
    # executing in the browser. Short TTL: uploads can be replaced in place.
    response.headers['Content-Disposition'] = f'inline; filename="{full.name}"'
    response.headers['Cache-Control'] = 'public, max-age=86400'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
