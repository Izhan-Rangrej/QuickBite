"""Tests for the production/deploy surface: DATABASE_URL parsing (Neon), the
health probe, media serving, and the seed-media restore used by ``build.sh``.

Run with:  python manage.py test core.tests_deploy -v 2
"""

import io
import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from quickbite.db import DatabaseURLError, database_config_from_url, parse_database_url

NEON_DIRECT = ('postgresql://neondb_owner:MyPass123@'
               'ep-cool-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require')
NEON_POOLED = NEON_DIRECT.replace('.ap-southeast-1', '-pooler.ap-southeast-1')


class DatabaseDown(Exception):
    """Stands in for a psycopg failure, e.g. while Neon's compute is waking up."""


class _DatabaseDownProxy:
    """Replacement for `core.ops.connection` that behaves like a dead database.

    Patching `django.db.connection` directly does not work: it is a proxy onto a
    context-local `DatabaseWrapper`, so a patch applied in the test's context is not
    the object the request handler resolves. Replacing the name the view looks up is
    exact, and it fails loudly if the view stops using it.
    """

    vendor = 'sqlite3'

    def ensure_connection(self):
        raise DatabaseDown('connection to server at "ep-cool-name" failed: timeout expired')

    def cursor(self):                      # pragma: no cover — never reached
        raise AssertionError('cursor() must not be used when ensure_connection() failed')


class ParseDatabaseUrlTests(SimpleTestCase):
    """`DATABASE_URL` is the one setting that can silently break a deploy."""

    def test_neon_direct_url(self):
        cfg = parse_database_url(NEON_DIRECT)
        self.assertEqual(cfg['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(cfg['NAME'], 'neondb')                 # NOT 'neondb?sslmode=require'
        self.assertEqual(cfg['USER'], 'neondb_owner')
        self.assertEqual(cfg['PASSWORD'], 'MyPass123')
        self.assertEqual(cfg['HOST'], 'ep-cool-name-123456.ap-southeast-1.aws.neon.tech')
        self.assertEqual(cfg['PORT'], '5432')
        self.assertEqual(cfg['OPTIONS']['sslmode'], 'require')

    def test_neon_without_sslmode_still_uses_tls(self):
        cfg = parse_database_url(NEON_DIRECT.split('?')[0])
        self.assertEqual(cfg['OPTIONS']['sslmode'], 'require')

    def test_explicit_sslmode_is_not_overridden(self):
        cfg = parse_database_url(NEON_DIRECT.replace('sslmode=require', 'sslmode=verify-full'))
        self.assertEqual(cfg['OPTIONS']['sslmode'], 'verify-full')

    def test_query_params_become_driver_options(self):
        cfg = parse_database_url(NEON_DIRECT + '&connect_timeout=15&application_name=quickbite')
        self.assertEqual(cfg['OPTIONS']['connect_timeout'], '15')
        self.assertEqual(cfg['OPTIONS']['application_name'], 'quickbite')
        self.assertEqual(cfg['NAME'], 'neondb')

    def test_percent_encoded_password_with_reserved_characters(self):
        cfg = parse_database_url('postgres://u:p%40ss%3Awo%2Frd@ep-x.us-east-2.aws.neon.tech/db')
        self.assertEqual(cfg['PASSWORD'], 'p@ss:wo/rd')
        self.assertEqual(cfg['NAME'], 'db')

    def test_at_sign_in_raw_password_does_not_confuse_the_host(self):
        # urlsplit splits credentials on the LAST '@', unlike a naive regex.
        cfg = parse_database_url('postgres://u:p@ss@ep-x.us-east-2.aws.neon.tech/db?sslmode=require')
        self.assertEqual((cfg['USER'], cfg['PASSWORD'], cfg['HOST']),
                         ('u', 'p@ss', 'ep-x.us-east-2.aws.neon.tech'))

    def test_pooler_endpoint_disables_session_features(self):
        cfg = parse_database_url(NEON_POOLED)
        self.assertIs(cfg['DISABLE_SERVER_SIDE_CURSORS'], True)
        self.assertIsNone(cfg['OPTIONS']['prepare_threshold'])   # PgBouncer transaction mode

    def test_direct_endpoint_keeps_server_side_cursors(self):
        cfg = parse_database_url(NEON_DIRECT)
        self.assertNotIn('DISABLE_SERVER_SIDE_CURSORS', cfg)
        self.assertNotIn('prepare_threshold', cfg.get('OPTIONS', {}))

    def test_legacy_postgres_scheme_and_default_port(self):
        cfg = parse_database_url('postgres://u:p@localhost/mydb')
        self.assertEqual((cfg['HOST'], cfg['PORT'], cfg['NAME']), ('localhost', '5432', 'mydb'))
        self.assertNotIn('OPTIONS', cfg)      # local Postgres must not be forced into TLS

    def test_django_own_params_in_query_string_are_applied(self):
        cfg = parse_database_url(NEON_DIRECT + '&CONN_MAX_AGE=0&conn_health_checks=false')
        self.assertEqual(cfg['CONN_MAX_AGE'], 0)
        self.assertIs(cfg['CONN_HEALTH_CHECKS'], False)
        self.assertNotIn('CONN_MAX_AGE', cfg['OPTIONS'])

    def test_sqlite_urls(self):
        self.assertEqual(parse_database_url('sqlite:///db.sqlite3')['NAME'], 'db.sqlite3')
        self.assertEqual(parse_database_url('/data/db.sqlite3')['NAME'], '/data/db.sqlite3')
        self.assertEqual(parse_database_url('sqlite:////data/db.sqlite3')['NAME'], '/data/db.sqlite3')

    def test_bad_scheme_message_names_the_expected_shape(self):
        with self.assertRaises(DatabaseURLError) as ctx:
            parse_database_url('mysql://u:p@host/db')
        self.assertIn('postgresql://', str(ctx.exception))

    def test_bare_host_is_rejected_instead_of_silently_using_sqlite(self):
        """Pasting Neon's "Host" box alone must fail loudly, not open an empty SQLite file."""
        for bad in ('ep-cool-name.ap-southeast-1.aws.neon.tech/neondb',
                    'quickbite.example.com/db'):
            with self.subTest(bad=bad):
                with self.assertRaises(DatabaseURLError) as ctx:
                    parse_database_url(bad)
                self.assertIn('must start with postgres://', str(ctx.exception))

    def test_settings_helper_propagates_a_schemeless_value(self):
        with self.assertRaises(DatabaseURLError):
            database_config_from_url('ep-x.ap-southeast-1.aws.neon.tech/neondb',
                                     sqlite_name=Path('/app/db.sqlite3'))

    def test_missing_database_name_raises(self):
        with self.assertRaises(DatabaseURLError):
            parse_database_url('postgresql://u:p@ep-x.us-east-2.aws.neon.tech')

    def test_error_message_never_leaks_the_password(self):
        with self.assertRaises(DatabaseURLError) as ctx:
            parse_database_url('postgresql://u:sup3rs3cr3t@ep-x.us-east-2.aws.neon.tech')
        self.assertNotIn('sup3rs3cr3t', str(ctx.exception))

    def test_settings_helper_falls_back_to_sqlite_when_unset(self):
        cfg = database_config_from_url('', sqlite_name=Path('/app/db.sqlite3'))
        self.assertEqual(cfg['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(Path(cfg['NAME']), Path('/app/db.sqlite3'))

    def test_settings_helper_applies_pooling_defaults(self):
        cfg = database_config_from_url(NEON_DIRECT, sqlite_name=Path('/app/db.sqlite3'),
                                       conn_max_age=60, conn_health_checks=True)
        self.assertEqual(cfg['CONN_MAX_AGE'], 60)
        self.assertIs(cfg['CONN_HEALTH_CHECKS'], True)

    def test_relative_sqlite_url_stays_next_to_the_default_database(self):
        cfg = database_config_from_url('sqlite:///other.sqlite3', sqlite_name=Path('/app/db.sqlite3'))
        self.assertEqual(Path(cfg['NAME']), Path('/app/other.sqlite3'))


class CsrfOriginNormalisationTests(SimpleTestCase):
    """A mistyped SITE_URL must not 403 a checkout or fail `manage.py check`."""

    def test_forms(self):
        from quickbite.settings import _csrf_origin
        cases = {
            'https://quickbite.onrender.com': 'https://quickbite.onrender.com',
            'https://quickbite.onrender.com/': 'https://quickbite.onrender.com',
            'quickbite.com': 'https://quickbite.com',                 # bare host → https
            'https://quickbite.com/zh/': 'https://quickbite.com',     # path is not allowed
            'ftp://quickbite.com': '',                                 # rejected, not fatal
            '': '',
        }
        for given, expected in cases.items():
            with self.subTest(given=given):
                self.assertEqual(_csrf_origin(given), expected)

    def test_blank_and_junk_env_values_fall_back_to_defaults(self):
        """`_flag` reads the environment, and Render happily leaves a box blank."""
        import os
        from quickbite.settings import _flag
        for value, expected in (('', 60), ('   ', 60), ('0', 0), ('30', 30), ('nonsense', 60)):
            with mock.patch.dict(os.environ, {'DB_CONN_MAX_AGE': value}):
                with self.subTest(value=repr(value)):
                    self.assertEqual(_flag('DB_CONN_MAX_AGE', 60), expected)
        for value, expected in (('', True), ('False', False), ('false', False), ('True', True), ('0', False)):
            with mock.patch.dict(os.environ, {'DB_CONN_HEALTH_CHECKS': value}):
                with self.subTest(value=repr(value)):
                    self.assertIs(_flag('DB_CONN_HEALTH_CHECKS', True), expected)


class HealthzTests(TestCase):
    """Render's health check path must be fast, unauthenticated and restart-proof."""

    def test_ok_when_database_responds(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['database'], 'ok')
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_transient_database_error_does_not_fail_the_probe(self):
        """A cold/suspending Neon must not make Render restart the instance in a loop."""
        with mock.patch('core.ops.connection', _DatabaseDownProxy()):
            response = self.client.get('/healthz')
            body = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body['status'], 'degraded')
        self.assertEqual(body['database'], 'error')
        self.assertIn('timeout expired', body['database_error'])

    def test_readiness_mode_reports_503(self):
        with mock.patch('core.ops.connection', _DatabaseDownProxy()):
            response = self.client.get('/healthz', {'db': '1'})
        self.assertEqual(response.status_code, 503)
        body = json.loads(response.content)
        self.assertEqual(body['database'], 'error')
        self.assertIn('database_error', body)

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True)
    def test_health_check_is_exempt_from_the_https_redirect(self):
        """Render probes over plain HTTP; a 301 would pass as "healthy" while
        proving nothing, so /healthz must answer 200 even when SSL is enforced."""
        self.assertEqual(self.client.get('/healthz').status_code, 200)
        self.assertEqual(self.client.get('/', secure=False).status_code, 301)
        self.assertEqual(self.client.get('/', secure=True).status_code, 200)

    def test_only_get_and_head_are_allowed(self):
        self.assertEqual(self.client.post('/healthz').status_code, 405)
        self.assertEqual(self.client.head('/healthz').status_code, 200)

    def test_needs_no_login_and_is_not_in_the_sitemap(self):
        from core.sitemaps import StaticViewSitemap
        self.assertEqual(self.client.get('/healthz').status_code, 200)
        self.assertNotIn('core:healthz', StaticViewSitemap().items())


class ServeMediaTests(TestCase):
    def setUp(self):
        self.media_root = Path(tempfile.mkdtemp(prefix='qb-media-'))
        self.addCleanup(shutil.rmtree, self.media_root, True)
        (self.media_root / 'dishes').mkdir()
        # A stub PNG; contents don't matter, only that the view streams a real file.
        self.target = self.media_root / 'dishes' / 'margherita.png'
        self.target.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 32)
        self.override = override_settings(MEDIA_ROOT=str(self.media_root), DEBUG=False)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_image_is_served_with_cache_headers(self):
        response = self.client.get('/media/dishes/margherita.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('max-age=86400', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('inline', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content).count(b'0'), 32)
        response.close()

    def test_head_is_supported_for_link_checkers(self):
        self.assertEqual(self.client.head('/media/dishes/margherita.png').status_code, 200)

    def test_missing_file_is_404(self):
        self.assertEqual(self.client.get('/media/dishes/nope.png').status_code, 404)

    def test_non_image_extension_is_refused_even_if_the_file_exists(self):
        (self.media_root / 'dishes' / 'evil.html').write_text('<script>alert(1)</script>')
        (self.media_root / 'dishes' / 'evil.svg').write_text('<svg onload="alert(1)"/>')
        for name in ('evil.html', 'evil.svg'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(f'/media/dishes/{name}').status_code, 404)

    def test_directory_is_not_listed(self):
        self.assertEqual(self.client.get('/media/dishes/').status_code, 404)

    def test_path_traversal_is_refused(self):
        secret = self.media_root.parent / 'secret.png'
        secret.write_bytes(b'not-yours')
        self.addCleanup(secret.unlink, True)
        for path in ('/media/../secret.png',
                     '/media/..%2Fsecret.png',
                     '/media/dishes/../../secret.png',
                     '/media/..%2f..%2fetc/passwd'):
            with self.subTest(path=path):
                # 400 = Django's own security middleware caught it first — also fine.
                self.assertIn(self.client.get(path).status_code, (400, 404))


class RestoreSeedMediaTests(TestCase):
    """build.sh relies on this to keep images alive across Render redeploys."""

    def setUp(self):
        from core.models import Category, Restaurant
        self.Category, self.Restaurant = Category, Restaurant
        self.media_root = Path(tempfile.mkdtemp(prefix='qb-restore-'))
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.override = override_settings(MEDIA_ROOT=str(self.media_root))
        self.override.enable()
        self.addCleanup(self.override.disable)

    def out(self):
        return io.StringIO()

    def test_missing_seed_image_is_recopied_from_static(self):
        restaurant = self.Restaurant.objects.create(
            name='Pizza Palace', address='1 MG Road', phone='9876543210')
        restaurant.image.name = 'restaurants/cat_pizza.jpg'
        restaurant.save()
        self.assertFalse((self.media_root / 'restaurants' / 'cat_pizza.jpg').exists())

        call_command('restore_seed_media', stdout=self.out())

        self.assertTrue((self.media_root / 'restaurants' / 'cat_pizza.jpg').is_file())

    def test_random_suffixed_name_falls_back_to_the_bundled_file(self):
        category = self.Category.objects.create(name='Pizza')
        category.image.name = 'categories/cat_pizza_a1b2c3d.jpg'
        category.save()

        call_command('restore_seed_media', stdout=self.out())

        self.assertTrue((self.media_root / 'categories' / 'cat_pizza_a1b2c3d.jpg').is_file())

    def test_existing_file_is_left_untouched(self):
        (self.media_root / 'categories').mkdir()
        mine = self.media_root / 'categories' / 'cat_pizza.jpg'
        mine.write_bytes(b'user-uploaded')
        category = self.Category.objects.create(name='Pizza')
        category.image.name = 'categories/cat_pizza.jpg'
        category.save()

        call_command('restore_seed_media', stdout=self.out())

        self.assertEqual(mine.read_bytes(), b'user-uploaded')

    def test_dry_run_writes_nothing(self):
        category = self.Category.objects.create(name='Burgers')
        category.image.name = 'categories/cat_burgers.jpg'
        category.save()

        call_command('restore_seed_media', dry_run=True, stdout=self.out())

        self.assertFalse((self.media_root / 'categories' / 'cat_burgers.jpg').exists())

    def test_empty_database_is_not_an_error(self):
        out = self.out()
        call_command('restore_seed_media', stdout=out)
        self.assertIn('referenced by the database: 0', out.getvalue())


class ErrorPageResilienceTests(TestCase):
    """Once public, the app is probed hourly by bots with foreign `Host` headers and
    junk cookies. Those requests are rejected *before* the session/auth middleware
    runs — and since every template (including the error pages) executes the context
    processors, an unguarded `request.user`/`request.session` turns a polite 400
    into a 500. That also poisons uptime checks, so it is asserted here."""

    @override_settings(ALLOWED_HOSTS=['quickbite.onrender.com'])
    def test_disallowed_host_renders_the_themed_400_page(self):
        response = self.client.get('/', HTTP_HOST='scanner.example.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn("That request didn't parse", response.content.decode())

    @override_settings(ALLOWED_HOSTS=['quickbite.onrender.com'])
    def test_context_processors_tolerate_a_bare_request(self):
        from django.test import RequestFactory
        from cart.context_processors import cart_data
        from core.context_processors import delivery_location, seo_defaults
        request = RequestFactory().get('/')      # no session, no user attributes
        self.assertEqual(cart_data(request)['cart_count'], 0)
        self.assertEqual(cart_data(request)['wishlist_ids'], set())
        self.assertFalse(delivery_location(request)['has_location'])
        self.assertEqual(seo_defaults(request)['site_name'], 'QuickBite')
