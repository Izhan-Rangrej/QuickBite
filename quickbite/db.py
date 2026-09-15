"""Turn a ``DATABASE_URL`` into a Django ``DATABASES`` entry.

Why this module exists instead of a one-line regex
--------------------------------------------------
Production runs on **Neon** (serverless PostgreSQL), whose connection strings are
messier than the textbook ``postgres://user:pass@host:5432/db``:

* They carry query parameters — ``?sslmode=require`` (mandatory) plus often
  ``connect_timeout`` / ``channel_binding`` / ``options``. A naive regex swallows
  ``db?sslmode=require`` *as the database name*, and the connection then dies with
  a confusing `database "db?sslmode=require" does not exist`.
* Passwords may contain ``@`` ``:`` ``/`` (Neon generates them) and must be
  percent-decoded before use.
* Pooled endpoints (``…-pooler.<region>.aws.neon.tech``) sit behind PgBouncer in
  transaction mode, so server-side cursors and auto-prepared statements must go off.

Everything here is pure Python and unit-tested in ``core/tests_deploy.py``.
"""

from urllib.parse import parse_qsl, unquote, urlsplit

#: URL schemes accepted for PostgreSQL.
PG_SCHEMES = {'postgres', 'postgresql', 'pgsql'}

#: Options Django consumes itself rather than passing to the driver.
DJANGO_OWN_KEYS = {
    'CONN_MAX_AGE', 'CONN_HEALTH_CHECKS', 'DISABLE_SERVER_SIDE_CURSORS',
    'ATOMIC_REQUESTS', 'AUTOCOMMIT', 'TIME_ZONE',
}

#: Query-string keys mapped onto the key psycopg/libpq expects in ``OPTIONS``.
#: Anything not listed is forwarded unchanged — libpq reports unknown keys itself.
PG_PARAM_ALIASES = {
    'sslmode': 'sslmode',
    'sslrootcert': 'sslrootcert',
    'sslcert': 'sslcert',
    'sslkey': 'sslkey',
    'channel_binding': 'channel_binding',
    'connect_timeout': 'connect_timeout',
    'application_name': 'application_name',
    'keepalives': 'keepalives',
    'keepalives_idle': 'keepalives_idle',
    'keepalives_interval': 'keepalives_interval',
    'keepalives_count': 'keepalives_count',
    'target_session_attrs': 'target_session_attrs',
}


class DatabaseURLError(RuntimeError):
    """Raised for a malformed/unsupported ``DATABASE_URL``.

    The message is written for a human staring at a Render build log: it shows the
    *shape* of the URL that was expected and never echoes the password.
    """


def _mask(url):
    """``postgres://u:pw@host/db`` → ``postgres://u:***@host/db`` for error text."""
    try:
        password = urlsplit(url).password
    except ValueError:
        return url
    if password:
        return url.replace(f':{password}@', ':***@', 1)
    return url


def _scheme(url):
    try:
        return urlsplit(url).scheme.lower()
    except ValueError as exc:  # e.g. an out-of-range port
        raise DatabaseURLError(f'DATABASE_URL is not a valid URL ({exc}).') from exc


def is_sqlite_url(url):
    """True for ``sqlite:///path``, ``sqlite:////abs/path`` or a bare ``*.sqlite3`` path."""
    url = (url or '').strip()
    return url.split(':', 1)[0].lower() == 'sqlite' or url.endswith(('.sqlite3', '.sqlite'))


def _sqlite_path(url):
    """Django/dj-database-url convention: three slashes = relative, four = absolute.

    ``sqlite:///db.sqlite3``       → ``db.sqlite3``      (relative to BASE_DIR)
    ``sqlite:////data/db.sqlite3`` → ``/data/db.sqlite3``
    ``/data/db.sqlite3``           → passed through (a bare path also works)
    """
    if ':' not in url or url.startswith('/'):
        return unquote(url.strip())
    tail = url.split(':', 1)[1]
    if not tail.startswith('//'):          # not a URL we understand — treat as a path
        return unquote(tail.strip())
    slashes = len(tail) - len(tail.lstrip('/'))
    path = unquote(tail.lstrip('/'))
    return '/' + path if slashes >= 4 else path


def parse_database_url(url):
    """Return a Django ``DATABASES['default']``-shaped dict parsed from ``url``.

    * ``sqlite`` URLs and bare paths → SQLite config
    * ``postgres(ql)`` URLs → PostgreSQL config: query params are split off the
      database name, credentials are percent-decoded, driver options go to
      ``OPTIONS``, and Neon-specific defaults are applied.
    """
    url = (url or '').strip()
    if not url:
        raise DatabaseURLError('parse_database_url() needs a non-empty URL.')

    scheme = _scheme(url)

    if scheme == 'sqlite' or is_sqlite_url(url):
        path = _sqlite_path(url)
        if not path:
            raise DatabaseURLError('SQLite URL must include a file path, e.g. sqlite:///db.sqlite3')
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': path}

    if scheme not in PG_SCHEMES:
        # A scheme-less value is usually someone pasting Neon's *Host* box
        # ("ep-xxx.ap-southeast-1.aws.neon.tech") instead of the full URL. Silently
        # falling back to SQLite here would look like the app "lost" its data.
        raise DatabaseURLError(
            'DATABASE_URL must start with postgres:// or postgresql:// '
            f'(got "{scheme or "no scheme"}"). Copy the whole string from Neon, e.g. '
            'postgresql://user:***@ep-cool-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
        )

    parts = urlsplit(url)

    if not parts.hostname:
        raise DatabaseURLError(
            'DATABASE_URL has no host. Expected '
            'postgres://user:password@host:5432/dbname?sslmode=require — paste the '
            'entire string from Neon (Database → Connection details), not just the host.'
        )
    if not parts.path or parts.path == '/':
        raise DatabaseURLError(
            f'DATABASE_URL has no database name. Expected …@{parts.hostname}:5432/<dbname> '
            f'(got "{_mask(url)}").'
        )

    dbname = unquote(parts.path.lstrip('/'))
    options = {}
    django_own = {}

    for raw_key, raw_value in parse_qsl(parts.query, keep_blank_values=True):
        key = raw_key.strip().lower()
        value = raw_value.strip()
        if not value:
            continue
        if key.upper() in DJANGO_OWN_KEYS:          # e.g. ?CONN_MAX_AGE=0
            django_own[key.upper()] = value
            continue
        options[PG_PARAM_ALIASES.get(key, key)] = unquote(value)

    host = (parts.hostname or '').lower()
    is_neon = host.endswith('.neon.tech')

    config = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': dbname,
        'USER': unquote(parts.username) if parts.username else '',
        'PASSWORD': unquote(parts.password) if parts.password else '',
        'HOST': parts.hostname,
        'PORT': str(parts.port) if parts.port else '5432',
    }

    # Neon *requires* TLS and normally states it in the URL; add it for bare hosts
    # and never downgrade an explicit choice.
    if 'sslmode' not in options and is_neon:
        options['sslmode'] = 'require'

    # A `-pooler` endpoint is PgBouncer in transaction mode: server connections are
    # swapped between transactions, so session-level features break. Turn off
    # Django's server-side cursors and psycopg3's auto-prepared statements
    # (otherwise: `prepared statement "s1" already exists`).
    if is_neon and ('-pooler' in host or host.startswith('pooler.')):
        django_own.setdefault('DISABLE_SERVER_SIDE_CURSORS', True)
        options.setdefault('prepare_threshold', None)

    if options:
        config['OPTIONS'] = options
    for key, value in django_own.items():
        if key == 'CONN_MAX_AGE':
            value = int(float(value))
        elif key in ('DISABLE_SERVER_SIDE_CURSORS', 'CONN_HEALTH_CHECKS'):
            value = value.lower() in ('1', 'true', 'yes', 'on') if isinstance(value, str) else bool(value)
        config[key.upper()] = value
    return config


def database_config_from_url(url, *, sqlite_name, conn_max_age=0, conn_health_checks=False):
    """Settings-layer helper: parse ``url``, or fall back to local SQLite.

    ``sqlite_name`` is the developer default (``BASE_DIR / 'db.sqlite3'``); a
    relative path from a ``sqlite:`` URL is resolved against it so local runs
    behave the same as the empty-``DATABASE_URL`` case.
    """
    url = (url or '').strip()
    if not url:
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': sqlite_name}

    config = parse_database_url(url)

    if config['ENGINE'] == 'django.db.backends.sqlite3':
        name = str(config['NAME'])
        if not name.startswith('/'):
            from pathlib import Path
            base = Path(sqlite_name).parent
            candidate = (base / name).resolve()
            candidate.relative_to(base.resolve())        # guard: keep it under BASE_DIR
            name = str(candidate)
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': name}

    # Persistent connections are a win against Neon's per-connection latency, but
    # a pooled (PgBouncer) endpoint must not be pinned by them.
    config.setdefault('CONN_MAX_AGE', conn_max_age)
    config.setdefault('CONN_HEALTH_CHECKS', bool(conn_health_checks))
    return config
