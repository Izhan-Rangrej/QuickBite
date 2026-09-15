"""Phase 9 verification — search, filters, location (run: python3 manage.py test core.tests_phase9)."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Category, Dish, Restaurant

User = get_user_model()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='u1', email='u1@test.com', password='pw123456')
        cls.rest = Restaurant.objects.create(
            name='Pizza Palace', address='1 Street', phone='9999999999',
            cuisine_type='pizza', rating=Decimal('4.5'), delivery_time=30,
            latitude=22.3110, longitude=73.1870)
        cls.rest2 = Restaurant.objects.create(
            name='Biryani House', address='2 Road', phone='9999999998',
            cuisine_type='indian', rating=Decimal('4.8'), delivery_time=35)
        cat = Category.objects.create(name='Pizza')
        cls.veg_dish = Dish.objects.create(
            name='Margherita Pizza', restaurant=cls.rest, category=cat,
            price=Decimal('349'), discount_price=Decimal('199'),
            rating=Decimal('4.5'), is_veg=True, preparation_time=25)
        cls.nonveg_dish = Dish.objects.create(
            name='Chicken Fiesta', restaurant=cls.rest, category=cat,
            price=Decimal('499'), rating=Decimal('3.9'), is_veg=False,
            preparation_time=30)
        cls.slow_dish = Dish.objects.create(
            name='Hyderabadi Biryani', restaurant=cls.rest2, category=cat,
            price=Decimal('299'), rating=Decimal('4.6'), is_veg=False,
            preparation_time=35)

    def setUp(self):
        self.client = Client()


class TestSearch(Base):
    def test_results_page_sections(self):
        r = self.client.get(reverse('core:search'), {'q': 'pizza'})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Margherita Pizza', html)     # dish section
        self.assertIn('Pizza Palace', html)          # restaurant section
        self.assertIn('qb-search-section', html)

    def test_no_results_state_with_suggestions(self):
        r = self.client.get(reverse('core:search'), {'q': 'zzzznotfound'})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('No results for', html)
        self.assertIn('qb-suggest-card', html)       # suggested categories
        self.assertIn('Popular right now', html)

    def test_suggest_json(self):
        r = self.client.get(reverse('core:search_suggest'), {'q': 'piz'})
        data = json.loads(r.content)
        self.assertTrue(data['results'])
        types = {x['type'] for x in data['results']}
        self.assertIn('dish', types)
        self.assertTrue(all(x['url'] for x in data['results']))
        # too-short query returns nothing
        data = json.loads(self.client.get(reverse('core:search_suggest'), {'q': 'p'}).content)
        self.assertEqual(data['results'], [])


class TestMenuFilters(Base):
    def get(self, **params):
        params.setdefault('ajax', '1')
        return self.client.get(reverse('core:menu'), params).content.decode()

    def test_veg_filter(self):
        html = self.get(veg='1')
        self.assertIn('Margherita Pizza', html)
        self.assertNotIn('Chicken Fiesta', html)
        html = self.get(veg='0')
        self.assertIn('Chicken Fiesta', html)
        self.assertNotIn('Margherita Pizza', html)

    def test_price_and_rating_filters(self):
        html = self.get(max_price='300')
        self.assertIn('Margherita Pizza', html)       # eff price 199
        self.assertNotIn('Chicken Fiesta', html)      # 499
        html = self.get(rating='4.5')
        self.assertIn('Margherita Pizza', html)
        self.assertNotIn('Chicken Fiesta', html)      # 3.9

    def test_delivery_and_cuisine_filters(self):
        # Biryani House delivers in 35 min → its dish is excluded by ≤30
        html = self.get(delivery='30')
        self.assertIn('Margherita Pizza', html)
        self.assertNotIn('Hyderabadi Biryani', html)
        html = self.get(cuisines='indian')
        self.assertNotIn('Margherita Pizza', html)    # pizza restaurant excluded
        self.assertIn('Hyderabadi Biryani', html)

    def test_sort_price_asc(self):
        html = self.get(sort='price_asc')
        self.assertLess(html.index('Margherita Pizza'), html.index('Chicken Fiesta'))

    def test_ajax_partial_has_no_full_page(self):
        r = self.client.get(reverse('core:menu'), {'ajax': '1'})
        body = r.content.decode()
        self.assertNotIn('<html', body)
        self.assertIn('dishes-grid', body)
        full = self.client.get(reverse('core:menu')).content.decode()
        self.assertIn('<html', full)

    def test_active_tags(self):
        html = self.get(veg='1', rating='4.5')
        self.assertIn('qb-active-tags', html)
        self.assertIn('qb-tag', html)


class TestLocation(Base):
    def test_set_by_city_and_availability(self):
        r = self.client.post(reverse('core:location_set'),
                             json.dumps({'city': 'vadodara'}),
                             content_type='application/json')
        data = json.loads(r.content)
        self.assertTrue(data['ok'])
        self.assertTrue(data['delivers'], 'Vadodara is within range of the seeded coords')
        self.assertEqual(self.client.session['delivery_label'], 'Vadodara')

        # far-away city → not available
        r = self.client.post(reverse('core:location_set'),
                             json.dumps({'city': 'delhi'}),
                             content_type='application/json')
        data = json.loads(r.content)
        self.assertTrue(data['ok'])
        self.assertFalse(data['delivers'])

    def test_set_requires_coords_or_city(self):
        r = self.client.post(reverse('core:location_set'), json.dumps({}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_restaurant_page_shows_distance(self):
        self.client.post(reverse('core:location_set'),
                         json.dumps({'lat': 22.3072, 'lon': 73.1812, 'label': 'Home'}),
                         content_type='application/json')
        html = self.client.get(reverse('core:restaurants')).content.decode()
        self.assertIn('rest-distance', html)
        self.assertIn('km', html)

    def test_clear(self):
        self.client.post(reverse('core:location_set'),
                         json.dumps({'city': 'surat'}), content_type='application/json')
        self.client.post(reverse('core:location_clear'), {'next': '/'})
        self.assertIsNone(self.client.session.get('delivery_lat'))


class TestRegression(Base):
    def test_all_main_pages_ok(self):
        for url in ('/menu/', '/restaurants/', '/cart/', '/search/',
                    '/dish/margherita-pizza/', '/restaurant/pizza-palace/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)
