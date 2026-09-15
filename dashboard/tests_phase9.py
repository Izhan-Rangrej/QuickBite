"""Phase 9 verification — admin dashboard + owner panel (run: python3 manage.py test dashboard.tests_phase9)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Category, Coupon, Dish, Restaurant
from orders.models import Address, Order, OrderItem
from reviews.models import Review

User = get_user_model()
LOCMEM_MAIL = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}


@override_settings(MAILERS=LOCMEM_MAIL)
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username='boss', email='b@t.com',
                                             password='pw123456', is_staff=True, role='admin')
        cls.cust = User.objects.create_user(username='cust', email='c@t.com', password='pw123456')
        cls.owner = User.objects.create_user(username='own', email='o@t.com',
                                             password='pw123456', role='owner')
        cls.rest = Restaurant.objects.create(name='Pizza Palace', address='1 St',
                                             phone='9999999999', owner=cls.owner)
        cls.rest2 = Restaurant.objects.create(name='Biryani House', address='2 Rd', phone='9999999998')
        cat = Category.objects.create(name='Pizza')
        cls.dish = Dish.objects.create(name='Margherita', restaurant=cls.rest,
                                       category=cat, price=Decimal('199'))
        cls.dish2 = Dish.objects.create(name='Biryani', restaurant=cls.rest2,
                                        category=cat, price=Decimal('299'))
        addr = Address.objects.create(user=cls.cust, full_name='C', phone='9876543210',
                                      address_line1='1 St', city='C', state='S', pincode='390007')
        cls.order = Order.objects.create(
            user=cls.cust, address=addr, address_snapshot='1 St',
            subtotal=Decimal('199'), delivery_fee=Decimal('40'), tax=Decimal('9.95'),
            discount=Decimal('0'), total=Decimal('248.95'))
        OrderItem.objects.create(order=cls.order, dish=cls.dish, dish_name='Margherita',
                                 quantity=2, price=Decimal('199'))

    def setUp(self):
        self.client = Client()
        mail.outbox = []


class TestAccess(Base):
    def test_dashboard_requires_staff(self):
        for url in ('/dashboard/', '/dashboard/orders/', '/dashboard/restaurants/'):
            r = self.client.get(url)
            self.assertIn(r.status_code, (302, 403), url)
        self.client.force_login(self.cust)
        for url in ('/dashboard/', '/dashboard/orders/'):
            r = self.client.get(url)
            self.assertIn(r.status_code, (302, 403), url)

    def test_panel_requires_owner(self):
        r = self.client.get('/panel/')
        self.assertEqual(r.status_code, 302)
        self.client.force_login(self.cust)
        r = self.client.get('/panel/')
        self.assertEqual(r.status_code, 302)          # customer bounced home
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/panel/').status_code, 200)


class TestDashboard(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def test_home_stats_and_charts(self):
        r = self.client.get(reverse('dashboard:home'))
        html = r.content.decode()
        self.assertEqual(r.status_code, 200)
        for needle in ('chartData', 'revenueChart', 'statusChart', 'dishesChart',
                       'Orders today'):
            self.assertIn(needle, html, needle)
        self.assertIn('248.95', html.replace(',', ''), 'revenue should show the order total')

    def test_order_status_update_sends_email(self):
        r = self.client.post(
            reverse('dashboard:order_status_update', args=[self.order.order_id]),
            {'status': 'delivered'})
        self.assertEqual(r.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')
        self.assertIsNotNone(self.order.delivered_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Delivered', mail.outbox[0].subject)

    def test_restaurant_crud(self):
        r = self.client.post(reverse('dashboard:restaurant_new'), {
            'name': 'Sushi Bay', 'address': '9 Dock', 'phone': '9999900000',
            'cuisine_type': 'sushi', 'rating': '4.2', 'delivery_time': 25,
            'min_order': '199', 'offer_text': '', 'description': '',
            'is_active': 'on'})
        self.assertEqual(r.status_code, 302)
        rest = Restaurant.objects.get(name='Sushi Bay')
        self.assertTrue(rest.is_active)

        self.client.post(reverse('dashboard:restaurant_toggle', args=[rest.pk]))
        rest.refresh_from_db()
        self.assertFalse(rest.is_active)

        self.client.post(reverse('dashboard:restaurant_delete', args=[rest.pk]))
        self.assertFalse(Restaurant.objects.filter(pk=rest.pk).exists())

    def test_dish_toggle_and_delete(self):
        self.client.post(reverse('dashboard:dish_toggle', args=[self.dish.pk]))
        self.dish.refresh_from_db()
        self.assertFalse(self.dish.is_available)
        self.client.post(reverse('dashboard:dish_delete', args=[self.dish.pk]))
        self.assertFalse(Dish.objects.filter(pk=self.dish.pk).exists())

    def test_category_delete_guard(self):
        cat = self.dish.category
        r = self.client.post(reverse('dashboard:category_delete', args=[cat.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Category.objects.filter(pk=cat.pk).exists(), 'categories with dishes must not delete')

    def test_coupon_form_validation(self):
        r = self.client.post(reverse('dashboard:coupon_new'), {
            'code': 'BROKEN', 'title': 'No discount set', 'description': '',
            'min_order_amount': '0', 'valid_from': '2026-09-01T00:00',
            'valid_until': '2026-12-01T00:00', 'is_active': 'on'})
        self.assertEqual(r.status_code, 200, 'invalid form must re-render')
        self.assertFalse(Coupon.objects.filter(code='BROKEN').exists())

        r = self.client.post(reverse('dashboard:coupon_new'), {
            'code': 'NEW50', 'title': 'Half off', 'description': '',
            'discount_percentage': '50', 'min_order_amount': '199',
            'max_discount': '100', 'valid_from': '2026-09-01T00:00',
            'valid_until': '2026-12-01T00:00', 'is_active': 'on'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Coupon.objects.filter(code='NEW50').exists())

    def test_user_role_update_and_self_protection(self):
        self.client.post(reverse('dashboard:user_update', args=[self.cust.pk]),
                         {'role': 'owner', 'is_active': 'on'})
        self.cust.refresh_from_db()
        self.assertEqual(self.cust.role, 'owner')
        self.assertTrue(self.cust.is_active)
        # self-demotion / self-deactivation must be ignored
        self.client.post(reverse('dashboard:user_update', args=[self.staff.pk]), {'role': 'customer'})
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.role, 'admin')
        self.assertTrue(self.staff.is_active)

    def test_review_moderation(self):
        review = Review.objects.create(user=self.cust, restaurant=self.rest,
                                       rating=1, comment='rude', reported=True)
        self.client.post(reverse('dashboard:review_moderate', args=[review.pk]),
                         {'action': 'toggle'})
        review.refresh_from_db()
        self.assertFalse(review.is_approved and review.reported)
        self.client.post(reverse('dashboard:review_moderate', args=[review.pk]),
                         {'action': 'delete'})
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())


class TestOwnerPanel(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def test_overview_scoped(self):
        html = self.client.get(reverse('panel:home')).content.decode()
        self.assertIn('Pizza Palace', html)
        self.assertIn('earningsChart', html)

    def test_orders_only_own_restaurant(self):
        # an order with ONLY rest2 dishes must not appear
        addr = Address.objects.create(user=self.cust, full_name='C2', phone='9876543211',
                                      address_line1='2 Rd', city='C', state='S', pincode='390008')
        other = Order.objects.create(user=self.cust, address=addr, address_snapshot='2 Rd',
                                     subtotal=Decimal('299'), delivery_fee=Decimal('40'),
                                     tax=Decimal('14.95'), discount=Decimal('0'),
                                     total=Decimal('353.95'))
        OrderItem.objects.create(order=other, dish=self.dish2, dish_name='Biryani',
                                 quantity=1, price=Decimal('299'))
        html = self.client.get(reverse('panel:orders')).content.decode()
        self.assertIn(self.order.order_id, html)
        self.assertNotIn(other.order_id, html)

    def test_dish_update_scoped(self):
        # own dish toggles fine
        self.client.post(reverse('panel:dish_update', args=[self.dish.pk]), {'toggle': '1'})
        self.dish.refresh_from_db()
        self.assertFalse(self.dish.is_available)
        # other restaurant's dish → 404
        r = self.client.post(reverse('panel:dish_update', args=[self.dish2.pk]), {'toggle': '1'})
        self.assertEqual(r.status_code, 404)

    def test_price_update(self):
        self.client.post(reverse('panel:dish_update', args=[self.dish.pk]),
                         {'price': '249', 'discount_price': '179'})
        self.dish.refresh_from_db()
        self.assertEqual(self.dish.price, Decimal('249'))
        self.assertEqual(self.dish.discount_price, Decimal('179'))
