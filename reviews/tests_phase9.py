"""Phase 9 verification — reviews & ratings (run: python3 manage.py test reviews.tests_phase9)."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Category, Dish, Restaurant
from orders.models import Order, OrderItem
from reviews.models import Review

User = get_user_model()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='u1', email='u1@test.com', password='pw123456')
        cls.other = User.objects.create_user(username='u2', email='u2@test.com', password='pw123456')
        cls.rest = Restaurant.objects.create(name='Pizza Palace', address='1 St', phone='9999999999')
        cat = Category.objects.create(name='Pizza')
        cls.dish = Dish.objects.create(name='Margherita', restaurant=cls.rest, category=cat,
                                       price=Decimal('199'))

    def setUp(self):
        self.client = Client()

    def make_delivered_order(self, user=None):
        from orders.models import Address
        user = user or self.user
        address = Address.objects.create(
            user=user, full_name='Test', phone='9876543210', address_line1='1 St',
            city='Vadodara', state='Gujarat', pincode='390007')
        order = Order.objects.create(
            user=user, address=address, address_snapshot='1 St, Vadodara',
            subtotal=Decimal('199'), delivery_fee=Decimal('40'), tax=Decimal('9.95'),
            discount=Decimal('0'), total=Decimal('248.95'),
            status=Order.Status.DELIVERED)
        OrderItem.objects.create(order=order, dish=self.dish, dish_name=self.dish.name,
                                 quantity=1, price=Decimal('199'))
        return order


class TestReviewRules(Base):
    def test_login_required(self):
        r = self.client.post(reverse('reviews:add'), {
            'target_type': 'restaurant', 'target_id': self.rest.pk, 'rating': 5})
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])
        self.assertEqual(Review.objects.count(), 0)

    def test_dish_review_requires_delivered_order(self):
        self.client.force_login(self.user)
        # no order yet → blocked
        self.client.post(reverse('reviews:add'), {
            'target_type': 'dish', 'target_id': self.dish.pk, 'rating': 5,
            'next': '/'})
        self.assertEqual(Review.objects.count(), 0)

        order = self.make_delivered_order()
        self.client.post(reverse('reviews:add'), {
            'target_type': 'dish', 'target_id': self.dish.pk, 'rating': 5,
            'comment': 'Amazing!', 'order_id': order.order_id, 'next': '/'})
        review = Review.objects.get()
        self.assertEqual(review.rating, 5)
        self.assertTrue(review.is_verified)
        self.assertEqual(review.user, self.user)

    def test_cannot_review_someone_elses_order(self):
        order = self.make_delivered_order(user=self.other)
        self.client.force_login(self.user)
        self.client.post(reverse('reviews:add'), {
            'target_type': 'dish', 'target_id': self.dish.pk, 'rating': 5,
            'order_id': order.order_id, 'next': '/'})
        self.assertEqual(Review.objects.count(), 0)

    def test_undelivered_order_blocked(self):
        order = self.make_delivered_order()
        order.status = Order.Status.PREPARING
        order.save()
        self.client.force_login(self.user)
        self.client.post(reverse('reviews:add'), {
            'target_type': 'dish', 'target_id': self.dish.pk, 'rating': 5,
            'order_id': order.order_id, 'next': '/'})
        self.assertEqual(Review.objects.count(), 0)

    def test_duplicate_review_blocked(self):
        order = self.make_delivered_order()
        self.client.force_login(self.user)
        for _ in range(2):
            self.client.post(reverse('reviews:add'), {
                'target_type': 'dish', 'target_id': self.dish.pk, 'rating': 4,
                'order_id': order.order_id, 'next': '/'})
        self.assertEqual(Review.objects.count(), 1)

    def test_restaurant_review_any_user(self):
        self.client.force_login(self.user)
        self.client.post(reverse('reviews:add'), {
            'target_type': 'restaurant', 'target_id': self.rest.pk,
            'rating': 4, 'comment': 'Quick delivery', 'next': '/'})
        self.assertEqual(Review.objects.filter(restaurant=self.rest).count(), 1)

    def test_invalid_rating_rejected(self):
        self.client.force_login(self.user)
        self.client.post(reverse('reviews:add'), {
            'target_type': 'restaurant', 'target_id': self.rest.pk,
            'rating': 9, 'next': '/'})
        self.assertEqual(Review.objects.count(), 0)


class TestReviewInteractions(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.review = Review.objects.create(user=self.other, restaurant=self.rest, rating=4)

    def test_helpful_toggle(self):
        url = reverse('reviews:helpful', args=[self.review.pk])
        data = json.loads(self.client.post(url).content)
        self.assertTrue(data['ok'] and data['active'])
        self.assertEqual(data['helpful_count'], 1)
        data = json.loads(self.client.post(url).content)
        self.assertFalse(data['active'])
        self.assertEqual(data['helpful_count'], 0)

    def test_report(self):
        data = json.loads(self.client.post(reverse('reviews:report', args=[self.review.pk])).content)
        self.assertTrue(data['ok'])
        self.review.refresh_from_db()
        self.assertTrue(self.review.reported)

    def test_helpful_requires_login(self):
        self.client.logout()
        r = self.client.post(reverse('reviews:helpful', args=[self.review.pk]))
        self.assertEqual(r.status_code, 302)


class TestReviewDisplay(Base):
    def test_dish_page_shows_reviews_and_average(self):
        Review.objects.create(user=self.user, dish=self.dish, rating=5, comment='Best!')
        Review.objects.create(user=self.other, dish=self.dish, rating=3)
        r = self.client.get(reverse('core:dish_detail', args=[self.dish.slug]))
        html = r.content.decode()
        self.assertIn('Best!', html)
        self.assertIn('qb-review-card', html)
        self.assertIn('4', html)  # average 4.0 rendered
        ctx = r.context
        self.assertEqual(ctx['review_count'], 2)
        self.assertEqual(ctx['avg_rating'], 4.0)

    def test_restaurant_page_shows_reviews(self):
        Review.objects.create(user=self.user, restaurant=self.rest, rating=4, comment='Lovely place')
        r = self.client.get(reverse('core:restaurant_detail', args=[self.rest.slug]))
        self.assertIn('Lovely place', r.content.decode())

    def test_unapproved_review_hidden(self):
        Review.objects.create(user=self.user, dish=self.dish, rating=5,
                              comment='SECRET', is_approved=False)
        html = self.client.get(reverse('core:dish_detail', args=[self.dish.slug])).content.decode()
        self.assertNotIn('SECRET', html)

    def test_order_page_shows_rate_forms_when_delivered(self):
        order = self.make_delivered_order()
        self.client.force_login(self.user)
        html = self.client.get(reverse('orders:order_detail', args=[order.order_id])).content.decode()
        self.assertIn('Rate your order', html)
        self.assertIn('qb-star-input', html)
