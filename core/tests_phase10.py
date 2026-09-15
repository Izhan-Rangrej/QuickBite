"""Phase 10 verification — SEO, info pages, errors, security, perf tooling.

Run: python3 manage.py test core.tests_phase10
"""
import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core import mail
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Category, Coupon, Dish, Restaurant
from core.templatetags.static_min import static_min
from orders.models import Order

User = get_user_model()
LOCMEM_MAIL = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rest = Restaurant.objects.create(
            name='Pizza Palace', address='1 St', phone='9999999999',
            cuisine_type='pizza', rating=Decimal('4.5'), delivery_time=30,
            latitude=22.31, longitude=73.19)
        cls.cat = Category.objects.create(name='Pizza')
        cls.dish = Dish.objects.create(name='Margherita Pizza', restaurant=cls.rest,
                                       category=cls.cat, price=Decimal('199'))

    def setUp(self):
        self.client = Client()
        cache.clear()


class TestSEO(Base):
    def test_home_meta_and_structured_data(self):
        html = self.client.get(reverse('core:home')).content.decode()
        self.assertIn('name="description"', html)
        self.assertIn('property="og:title"', html)
        self.assertIn('property="og:image"', html)
        self.assertIn('application/ld+json', html)
        self.assertIn('rel="canonical"', html)

    def test_dish_page_og_product(self):
        html = self.client.get(self.dish.get_absolute_url()).content.decode()
        self.assertIn('"@type": "MenuItem"', html)
        self.assertIn('Margherita Pizza', html)

    def test_sitemap(self):
        r = self.client.get('/sitemap.xml')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('<urlset', body)
        self.assertIn('/menu/', body)
        self.assertIn(self.dish.get_absolute_url(), body)
        self.assertIn(self.rest.get_absolute_url(), body)

    def test_robots(self):
        r = self.client.get('/robots.txt')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('Disallow: /admin/', body)
        self.assertIn('Disallow: /dashboard/', body)
        self.assertIn('Sitemap:', body)


class TestInfoPages(Base):
    def test_all_render(self):
        for name in ('about', 'contact', 'faq', 'terms', 'privacy', 'refund'):
            r = self.client.get(reverse(f'core:{name}'))
            self.assertEqual(r.status_code, 200, name)

    def test_faq_has_accordion(self):
        html = self.client.get(reverse('core:faq')).content.decode()
        self.assertIn('qb-accordion', html)
        self.assertIn('How do I place an order?', html)

    def test_footer_links_wired(self):
        html = self.client.get(reverse('core:home')).content.decode()
        for url in ('/about/', '/contact/', '/faq/', '/terms/', '/privacy/',
                    '/refund-policy/', '/sitemap.xml'):
            self.assertIn(f'href="{url}"', html, url)

    @override_settings(MAILERS=LOCMEM_MAIL)
    def test_contact_form_sends_email(self):
        mail.outbox = []
        r = self.client.post(reverse('core:contact'), {
            'name': 'Test Person', 'email': 'tp@test.com', 'phone': '9876543210',
            'subject': 'feedback', 'message': 'Great app, love the tracking!'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Great app', mail.outbox[0].body)
        self.assertIn('tp@test.com', mail.outbox[0].body)

    @override_settings(MAILERS=LOCMEM_MAIL)
    def test_contact_form_validation(self):
        mail.outbox = []
        r = self.client.post(reverse('core:contact'), {
            'name': '', 'email': 'not-an-email', 'phone': '123',
            'subject': 'feedback', 'message': 'x'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(mail.outbox)
        self.assertContains(r, 'Enter a valid')


class TestErrorPages(Base):
    def test_404_page(self):
        r = self.client.get('/this-page-does-not-exist/')
        self.assertEqual(r.status_code, 404)
        html = r.content.decode()
        self.assertIn('404', html)
        self.assertIn('Go to Home', html)

    def test_handler_views_render(self):
        from core.error_views import bad_request, permission_denied, server_error

        from django.contrib.auth.models import AnonymousUser
        req = RequestFactory().get('/x')
        req.session = SessionStore()
        req._messages = FallbackStorage(req)
        req.user = AnonymousUser()
        self.assertEqual(bad_request(req).status_code, 400)
        self.assertEqual(permission_denied(req).status_code, 403)
        self.assertEqual(server_error(req).status_code, 500)


@override_settings(MAILERS=LOCMEM_MAIL)
class TestLoginRateLimiting(Base):
    def test_lockout_after_limit(self):
        for i in range(5):
            r = self.client.post(reverse('accounts:login'),
                                 {'username': 'nobody', 'password': 'wrong', })
            self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse('accounts:login'),
                             {'username': 'nobody', 'password': 'wrong'})
        self.assertContains(r, 'Too many failed login attempts')
        self.assertEqual(r.context['rate_limited'], True)

    def test_successful_login_resets_counter(self):
        user = User.objects.create_user(username='good', email='g@t.com', password='pw12345678')
        for _ in range(3):
            self.client.post(reverse('accounts:login'),
                             {'username': 'good', 'password': 'wrong'})
        r = self.client.post(reverse('accounts:login'),
                             {'username': 'good', 'password': 'pw12345678'})
        self.assertEqual(r.status_code, 302, 'valid login must succeed')
        # counter cleared → 5 more failures allowed
        for _ in range(5):
            self.client.logout()
            self.client.post(reverse('accounts:login'),
                             {'username': 'good', 'password': 'wrong'})


class TestStaticMinTag(TestCase):
    def test_prod_serves_dist(self):
        with self.settings(DEBUG=False):
            self.assertEqual(static_min('css/style.css'), '/static/dist/css/style.css')

    def test_dev_serves_original(self):
        with self.settings(DEBUG=True):
            self.assertEqual(static_min('css/style.css'), '/static/css/style.css')

    def test_already_minified_untouched(self):
        with self.settings(DEBUG=False):
            self.assertEqual(static_min('js/chart.umd.min.js'), '/static/js/chart.umd.min.js')


class TestModelUnits(Base):
    def test_order_id_format(self):
        from orders.models import Address
        user = User.objects.create_user(username='m1', email='m1@t.com', password='pw123456')
        addr = Address.objects.create(user=user, full_name='M', phone='9876543210',
                                      address_line1='X', city='C', state='S', pincode='390007')
        order = Order.objects.create(user=user, address=addr, address_snapshot='X',
                                     subtotal=Decimal('1'), delivery_fee=Decimal('0'),
                                     tax=Decimal('0'), discount=Decimal('0'),
                                     total=Decimal('1'))
        self.assertRegex(order.order_id, r'^QB\d{6}-[A-Z0-9]{6}$')

    def test_coupon_usage_limit(self):
        c = Coupon.objects.create(code='ONEUSE', title='t', discount_amount=Decimal('10'),
                                  usage_limit=1, used_count=0,
                                  valid_until=timezone.now() + timedelta(days=1))
        self.assertTrue(c.is_valid_now)
        c.used_count = 1
        self.assertFalse(c.is_valid_now)

    def test_haversine(self):
        self.assertEqual(self.rest.distance_km_from(22.31, 73.19), 0.0)
        self.assertIsNone(self.rest.distance_km_from(None, 73.19))
        # ~11 km north of the restaurant
        d = self.rest.distance_km_from(22.41, 73.19)
        self.assertTrue(10 < d < 12, d)
        self.assertEqual(self.rest.delivery_extra_minutes(4), 0)
        self.assertEqual(self.rest.delivery_extra_minutes(12), 10)
        self.assertEqual(self.rest.delivery_extra_minutes(100), 25)
