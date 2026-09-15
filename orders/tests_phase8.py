"""Phase 8 verification — checkout & orders (run: python3 manage.py test orders.tests_phase8)."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cart import service as cart_service
from core.models import Category, Coupon, Dish, Restaurant
from orders.models import Address, Order
from orders.service import CheckoutError, place_order

User = get_user_model()

LOCMEM_MAIL = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}

ADDR = {
    'full_name': 'Test Buyer', 'phone': '9876543210',
    'address_line1': '12 MG Road', 'address_line2': 'Near Tower',
    'city': 'Vadodara', 'state': 'Gujarat', 'pincode': '390007',
    'landmark': 'Big Mall', 'address_type': 'home', 'is_default': 'on',
}


@override_settings(MAILERS=LOCMEM_MAIL)
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='buyer', email='buyer@test.com', password='pw123456',
            first_name='Test', last_name='Buyer')
        cls.other = User.objects.create_user(
            username='other', email='other@test.com', password='pw123456')
        rest = Restaurant.objects.create(name='Pizza Hut Test', address='1 Street', phone='9999999999')
        cat = Category.objects.create(name='Pizza')
        cls.pizza = Dish.objects.create(name='Margherita', restaurant=rest, category=cat,
                                        price=Decimal('199.00'), preparation_time=25)
        cls.donut = Dish.objects.create(name='Donuts', restaurant=rest, category=cat,
                                        price=Decimal('149.00'), preparation_time=15)

    def setUp(self):
        self.client = Client()
        mail.outbox = []

    def make_address(self, **kw):
        data = dict(ADDR, **kw)
        data.pop('is_default', None)
        return Address.objects.create(user=self.user, is_default=kw.get('is_default', False), **data)

    def fill_cart(self):
        self.client.force_login(self.user)
        for dish_id, qty in ((self.pizza.pk, 1), (self.donut.pk, 1)):
            r = self.client.post(reverse('cart:cart_add'),
                                 {'dish_id': dish_id, 'quantity': qty},
                                 content_type='application/json')
            self.assertEqual(r.status_code, 200)


class TestAddress(Base):
    def test_first_address_auto_default_and_form_validation(self):
        a1 = self.make_address()
        a1.refresh_from_db()
        self.assertTrue(a1.is_default, 'first address must become default')
        a2 = self.make_address(address_line1='99 Race Course', is_default=True)
        a1.refresh_from_db()
        self.assertFalse(a1.is_default, 'setting a new default must unset the old one')
        self.assertTrue(a2.is_default)

        from orders.forms import AddressForm
        bad = AddressForm(dict(ADDR, pincode='12345', phone='12345', is_default=False))
        self.assertFalse(bad.is_valid())
        self.assertIn('pincode', bad.errors)
        self.assertIn('phone', bad.errors)
        good = AddressForm(dict(ADDR, is_default=False))
        self.assertTrue(good.is_valid(), good.errors)


class TestCheckout(Base):
    def test_login_required(self):
        r = self.client.get(reverse('orders:checkout'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login', r['Location'])

    def test_checkout_page_renders_three_steps(self):
        self.fill_cart()
        self.make_address()
        r = self.client.get(reverse('orders:checkout'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for needle in ('Delivery Address', 'Payment Method', 'Review & Place Order',
                       'Cash on Delivery', 'Coming Soon', 'Place Order',
                       'form="checkoutForm"', 'qb-steps-bar'):
            self.assertIn(needle, html, f'missing: {needle}')

    def test_place_order_full_flow(self):
        self.fill_cart()
        self.make_address()
        addr = Address.objects.get(user=self.user)
        # apply FIRST50-style coupon: 50% up to ₹100, min ₹199
        coupon = Coupon.objects.create(
            code='FIRST50', title='50% off', discount_percentage=Decimal('50'),
            max_discount=Decimal('100'), min_order_amount=Decimal('199'),
            valid_until=timezone.now() + timedelta(days=30))
        r = self.client.post(reverse('cart:coupon_apply'), {'code': 'FIRST50'},
                             content_type='application/json')
        self.assertEqual(r.json()['ok'], True)

        r = self.client.post(reverse('orders:checkout'), {
            'address_id': addr.pk, 'payment_method': 'cod',
            'instructions': 'Extra spicy please',
        })
        self.assertEqual(r.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertIn(f"/checkout/success/{order.order_id}/", r['Location'])

        # money: 348 subtotal − 100 coupon + 40 delivery + 5% of 248 tax
        self.assertEqual(order.subtotal, Decimal('348.00'))
        self.assertEqual(order.discount, Decimal('100.00'))
        self.assertEqual(order.delivery_fee, Decimal('40.00'))
        self.assertEqual(order.tax, Decimal('12.40'))
        self.assertEqual(order.total, Decimal('300.40'))
        self.assertEqual(order.coupon_code, 'FIRST50')
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.eta_minutes, 35)
        self.assertEqual(order.special_instructions, 'Extra spicy please')
        self.assertTrue(order.order_id.startswith('QB'))

        # snapshots
        items = {i.dish_name: i for i in order.items.all()}
        self.assertEqual(set(items), {'Margherita', 'Donuts'})
        self.assertEqual(items['Margherita'].price, Decimal('199.00'))
        self.assertEqual(items['Margherita'].sub_total, Decimal('199.00'))

        # cart + session coupon cleared, coupon usage counted
        cart_html = self.client.get(reverse('cart:cart_page')).content.decode()
        self.assertNotIn('Margherita', cart_html, 'cart must be empty after ordering')
        self.assertIsNone(self.client.session.get(cart_service.COUPON_SESSION_KEY))
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)

        # confirmation email
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.order_id, mail.outbox[0].subject)
        self.assertIn(order.order_id, mail.outbox[0].body)
        self.assertIn('buyer@test.com', mail.outbox[0].to)

        # success page
        r = self.client.get(r['Location'])
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('qb-check-mark', html)
        self.assertIn(order.order_id, html)

    def test_upi_and_empty_cart_rejected(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        addr = self.make_address()

        # empty cart
        req = rf.post('/checkout/')
        req.user = self.user
        req.session = self.client.session
        with self.assertRaises(CheckoutError):
            place_order(req, addr, 'cod')

        # upi not live yet
        self.fill_cart()
        req = rf.post('/checkout/')
        req.user = self.user
        req.session = self.client.session
        with self.assertRaises(CheckoutError):
            place_order(req, addr, 'upi')
        self.assertEqual(Order.objects.count(), 0)

    def test_coupon_revoked_between_apply_and_order(self):
        self.fill_cart()
        addr = self.make_address()
        coupon = Coupon.objects.create(
            code='FLASH', title='flash', discount_percentage=Decimal('20'),
            valid_until=timezone.now() + timedelta(days=1))
        self.client.post(reverse('cart:coupon_apply'), {'code': 'FLASH'},
                         content_type='application/json')
        coupon.is_active = False
        coupon.save()

        r = self.client.post(reverse('orders:checkout'),
                             {'address_id': addr.pk, 'payment_method': 'cod'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Order.objects.count(), 0, 'revoked coupon must block the order')
        self.assertIsNone(self.client.session.get(cart_service.COUPON_SESSION_KEY),
                          'revoked coupon must be dropped from the session')

    def test_usage_limit_blocks_reuse(self):
        coupon = Coupon.objects.create(
            code='ONCE', title='once', discount_amount=Decimal('50'),
            usage_limit=1, used_count=1,
            valid_until=timezone.now() + timedelta(days=1))
        self.assertFalse(coupon.is_valid_now)
        self.fill_cart()
        r = self.client.post(reverse('cart:coupon_apply'), {'code': 'ONCE'},
                             content_type='application/json')
        self.assertEqual(r.json()['ok'], False)


class TestOrderPages(Base):
    def place(self):
        self.fill_cart()
        self.make_address()
        addr = Address.objects.get(user=self.user)
        r = self.client.post(reverse('orders:checkout'),
                             {'address_id': addr.pk, 'payment_method': 'cod'})
        return Order.objects.get(user=self.user), r

    def test_my_orders_filter_search_and_navbar(self):
        order, _ = self.place()
        r = self.client.get(reverse('orders:my_orders'))
        self.assertEqual(r.status_code, 200)
        self.assertIn(order.order_id, r.content.decode())
        self.assertIn('qb-filter-chips', r.content.decode())

        r = self.client.get(reverse('orders:my_orders'), {'status': 'pending'})
        self.assertIn(order.order_id, r.content.decode())
        r = self.client.get(reverse('orders:my_orders'), {'status': 'delivered'})
        self.assertNotIn(order.order_id, r.content.decode())
        r = self.client.get(reverse('orders:my_orders'), {'q': order.order_id})
        self.assertIn(order.order_id, r.content.decode())
        r = self.client.get(reverse('orders:my_orders'), {'q': 'NOPE-000'})
        self.assertNotIn(order.order_id, r.content.decode())

        home = self.client.get(reverse('core:home')).content.decode()
        self.assertIn(reverse('orders:my_orders'), home, 'navbar must link My Orders')

    def test_detail_invoice_and_isolation(self):
        order, _ = self.place()
        r = self.client.get(reverse('orders:order_detail', args=[order.order_id]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for needle in ('qb-timeline', 'Bill Details', 'Delivery Address', 'Order Tracking'):
            self.assertIn(needle, html, f'missing: {needle}')

        r = self.client.get(reverse('orders:order_invoice', args=[order.order_id]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertIn(f'QuickBite-Invoice-{order.order_id}', r['Content-Disposition'])
        self.assertIn('TOTAL PAID', r.content.decode())

        self.client.logout()
        self.client.force_login(self.other)
        r = self.client.get(reverse('orders:order_detail', args=[order.order_id]))
        self.assertEqual(r.status_code, 404, "other user must not see the order")

    def test_cancel_and_reorder(self):
        order, _ = self.place()
        self.assertTrue(order.can_cancel)
        r = self.client.post(reverse('orders:order_cancel', args=[order.order_id]))
        self.assertEqual(r.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(len(mail.outbox), 2, 'confirmation + cancellation emails')

        # delivered orders can't be cancelled
        order.status = 'delivered'
        order.save()
        self.client.post(reverse('orders:order_cancel', args=[order.order_id]))
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')

        # reorder puts the dishes back in the cart (logged-in carts are DB-based)
        r = self.client.post(reverse('orders:order_reorder', args=[order.order_id]))
        self.assertEqual(r.status_code, 302)
        cart_html = self.client.get(reverse('cart:cart_page')).content.decode()
        self.assertIn('Margherita', cart_html)
        self.assertIn('Donuts', cart_html)


class TestAddressCRUD(Base):
    def test_add_edit_default_delete_endpoints(self):
        self.fill_cart()
        n0 = Address.objects.filter(user=self.user).count()

        # invalid add is rejected
        self.client.post(reverse('orders:address_add'),
                         dict(ADDR, pincode='123'), next='/checkout/')
        self.assertEqual(Address.objects.filter(user=self.user).count(), n0)

        # valid add redirects with ?select=<pk>
        r = self.client.post(reverse('orders:address_add'), dict(ADDR, next='/checkout/'))
        self.assertEqual(r.status_code, 302)
        a1 = Address.objects.get(user=self.user)
        self.assertIn(f'select={a1.pk}', r['Location'])

        # edit
        self.client.post(reverse('orders:address_edit', args=[a1.pk]),
                         dict(ADDR, city='Ahmedabad', next='/checkout/'))
        a1.refresh_from_db()
        self.assertEqual(a1.city, 'Ahmedabad')

        # set-default swaps
        a2 = Address.objects.create(user=self.user, full_name='Work Addr', phone='9876500011',
                                    address_line1='Office Park', city='Surat', state='Gujarat',
                                    pincode='395001', address_type='work')
        self.client.post(reverse('orders:address_set_default', args=[a2.pk]), next='/checkout/')
        a1.refresh_from_db(); a2.refresh_from_db()
        self.assertTrue(a2.is_default and not a1.is_default)

        # deleting the default promotes the next address
        self.client.post(reverse('orders:address_delete', args=[a2.pk]), next='/checkout/')
        a1.refresh_from_db()
        self.assertTrue(a1.is_default, 'deleting default must promote the next address')


class TestRegression(Base):
    def test_existing_pages_still_ok(self):
        for url in (reverse('core:home'), reverse('core:menu'), reverse('cart:cart_page')):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_timeline_states(self):
        order = Order.objects.create(
            user=self.user, address=self.make_address(), address_snapshot='x',
            subtotal=Decimal('100'), delivery_fee=Decimal('40'), tax=Decimal('5'),
            discount=Decimal('0'), total=Decimal('145'))
        steps = order.timeline_steps
        self.assertEqual(steps[0][2], 'current')
        self.assertTrue(all(s[2] == 'upcoming' for s in steps[1:]))
        order.status = 'delivered'
        steps = order.timeline_steps
        self.assertTrue(all(s[2] == 'done' for s in steps[:-1]))
        self.assertEqual(steps[-1][2], 'current')
        order.status = 'cancelled'
        self.assertEqual(order.timeline_steps, [])
