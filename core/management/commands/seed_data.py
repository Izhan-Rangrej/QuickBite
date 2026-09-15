"""
Seed QuickBite with the same data shown in the original HTML template
(Pizza Palace, Biryani House, Margherita Pizza ₹199/₹349, FIRST50, ...).

Usage:
    python manage.py seed_data          # idempotent — safe to re-run
    python manage.py seed_data --flush  # delete existing data first

Images are read from static/images/seed/ (bundled with the repo);
if a file is missing the record is still created, just without an image.
"""
from datetime import time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Category, Coupon, Dish, Restaurant

SEED_DIR = Path(settings.BASE_DIR) / 'static' / 'images' / 'seed'


def attach_image(obj, filename):
    """Copy a bundled seed file into MEDIA_ROOT via the model's ImageField."""
    path = SEED_DIR / filename
    if not path.exists():
        return False
    with open(path, 'rb') as fh:
        obj.image.save(filename, File(fh), save=False)
    return True


class Command(BaseCommand):
    help = 'Seed the database with QuickBite sample data (template-matching).'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true',
                            help='Delete all existing data before seeding')

    def handle(self, *args, **options):
        if options['flush']:
            Dish.objects.all().delete()
            Coupon.objects.all().delete()
            Restaurant.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING('Flushed existing data.'))

        # ---------------- CATEGORIES ----------------
        categories = {}
        cat_data = [
            ('Pizza',    'cat_pizza.jpg',    'Wood-fired and classic pizzas with gooey cheese.'),
            ('Burgers',  'cat_burgers.jpg',  'Juicy patties, brioche buns and special sauces.'),
            ('Sushi',    'cat_sushi.jpg',    'Fresh rolls, nigiri and sashimi platters.'),
            ('Biryani',  'cat_biryani.jpg',  'Aromatic dum-cooked biryanis and kebabs.'),
            ('Desserts', 'cat_desserts.jpg', 'Cakes, donuts, ice creams and more sweet treats.'),
            ('Thali',    'cat_thali.jpg',    'Complete meals with rice, sabzi, roti and sweets.'),
            ('Chinese',  'cat_chinese.jpg',  'Noodles, momos, Manchurian and wok specials.'),
            ('Rolls',    'cat_rolls.jpg',    'Kathi rolls, wraps and Frankie sandwiches.'),
        ]
        for name, img, desc in cat_data:
            cat, _ = Category.objects.get_or_create(
                name=name, defaults={'description': desc, 'is_active': True})
            if img and not cat.image:
                if attach_image(cat, img):
                    cat.save()
            categories[name.lower()] = cat
        self.stdout.write(f'Categories: {Category.objects.count()}')

        # ---------------- RESTAURANTS ----------------
        restaurants = {}
        rest_data = [
            # name, img, cuisine, rating, delivery, min_order, offer, promoted, address, phone, desc
            ('Pizza Palace', 'rest_pizza_palace.jpg', 'pizza', '4.5', 30, '199',
             '40% OFF up to ₹80', True, '12 Food Street, Bandra West, Mumbai',
             '+91 98765 43210', 'Authentic Italian pizzas baked in a wood-fired oven.'),
            ('Biryani House', 'rest_biryani_house.jpg', 'indian', '4.7', 35, '249',
             '₹125 OFF above ₹249', False, '45 MG Road, Andheri East, Mumbai',
             '+91 98765 43211', 'Legendary Hyderabadi dum biryani since 1998.'),
            ('Burger Barn', 'rest_burger_barn.jpg', 'burger', '4.8', 20, '149',
             '60% OFF up to ₹120', False, '7 Linking Road, Khar West, Mumbai',
             '+91 98765 43212', 'Smash burgers, loaded fries and thick shakes.'),
            ('Wok Express', 'rest_wok_express.jpg', 'chinese', '4.4', 25, '179',
             'Flat ₹100 OFF', False, '23 FC Road, Powai, Mumbai',
             '+91 98765 43213', 'Indo-Chinese wok tosses, noodles and momos.'),
            ('Sweet Spot', 'cat_desserts.jpg', 'dessert', '4.6', 15, '99',
             'Buy 1 Get 1 on donuts', False, '9 Hill Road, Bandra West, Mumbai',
             '+91 98765 43214', 'Freshly baked desserts, donuts and waffles.'),
            ('Desi Kitchen', 'cat_thali.jpg', 'thali', '4.9', 30, '199',
             'Free sweet with every thali', False, '56 SV Road, Juhu, Mumbai',
             '+91 98765 43215', 'Home-style thalis and North Indian classics.'),
        ]
        for (name, img, cuisine, rating, delivery, min_order,
             offer, promoted, address, phone, desc) in rest_data:
            rest, _ = Restaurant.objects.get_or_create(
                name=name,
                defaults={
                    'cuisine_type': cuisine, 'rating': Decimal(rating),
                    'delivery_time': delivery, 'min_order': Decimal(min_order),
                    'offer_text': offer, 'is_promoted': promoted,
                    'address': address, 'phone': phone, 'description': desc,
                    'opening_time': time(10, 0), 'closing_time': time(23, 30),
                    'is_active': True,
                })
            if img and not rest.image:
                if attach_image(rest, img):
                    rest.save()
            restaurants[name] = rest
        self.stdout.write(f'Restaurants: {Restaurant.objects.count()}')

        # ---------------- DISHES (exact template data) ----------------
        dish_data = [
            # name, img, restaurant, category, price(old), disc(sale), bestseller, new, veg, rating, prep
            ('Margherita Pizza', 'cat_pizza.jpg', 'Pizza Palace', 'pizza',
             '349', '199', True, False, True, '4.5', 25,
             'Classic delight with mozzarella cheese'),
            ('Classic Smash Burger', 'cat_burgers.jpg', 'Burger Barn', 'burgers',
             '449', '249', False, True, False, '4.8', 20,
             'Double patty with special sauce'),
            ('Hyderabadi Biryani', 'cat_biryani.jpg', 'Biryani House', 'biryani',
             '499', '299', True, False, False, '4.7', 35,
             'Aromatic basmati rice with tender chicken'),
            ('Chocolate Donuts', 'cat_desserts.jpg', 'Sweet Spot', 'desserts',
             '199', '149', False, False, True, '4.6', 15,
             'Freshly glazed chocolate donuts'),
            ('Hakka Noodles', 'cat_chinese.jpg', 'Wok Express', 'chinese',
             '299', '179', False, False, True, '4.4', 22,
             'Stir-fried noodles with vegetables'),
            ('Special Thali', 'cat_thali.jpg', 'Desi Kitchen', 'thali',
             '599', '349', False, True, True, '4.9', 30,
             'Complete meal with 8 items'),
        ]
        for (name, img, rest, cat, price, disc, bestseller, new,
             veg, rating, prep, desc) in dish_data:
            dish, _ = Dish.objects.get_or_create(
                name=name, restaurant=restaurants[rest],
                defaults={
                    'category': categories[cat], 'price': Decimal(price),
                    'discount_price': Decimal(disc), 'is_bestseller': bestseller,
                    'is_new': new, 'is_veg': veg, 'rating': Decimal(rating),
                    'preparation_time': prep, 'description': desc,
                    'is_available': True,
                })
            if img and not dish.image:
                if attach_image(dish, img):
                    dish.save()
        self.stdout.write(f'Dishes: {Dish.objects.count()}')

        # ---------------- COUPONS ----------------
        now = timezone.now()
        coupon_data = [
            # code, title, desc, pct, amt, min_order, max_disc, days_valid
            ('FIRST50', '50% off your first order',
             'Get 50% OFF on your first order. Maximum discount ₹100.',
             '50', None, '199', '100', 60),
            ('FREEDEL', 'Free delivery weekend special',
             'Flat ₹50 off (delivery fee) on orders above ₹299.',
             None, '50', '299', None, 30),
        ]
        for code, title, desc, pct, amt, min_order, max_disc, days in coupon_data:
            Coupon.objects.get_or_create(
                code=code,
                defaults={
                    'title': title, 'description': desc,
                    'discount_percentage': Decimal(pct) if pct else None,
                    'discount_amount': Decimal(amt) if amt else None,
                    'min_order_amount': Decimal(min_order),
                    'max_discount': Decimal(max_disc) if max_disc else None,
                    'valid_from': now - timedelta(days=1),
                    'valid_until': now + timedelta(days=days),
                    'is_active': True,
                })
        self.stdout.write(f'Coupons: {Coupon.objects.count()}')

        # ---------------- PHASE 9: coords, owner, reviews ----------------
        from django.contrib.auth import get_user_model

        from reviews.models import Review

        coords = {
            'Pizza Palace':  (22.3110, 73.1870),   # around Vadodara — matches the
            'Biryani House': (22.3020, 73.1955),   # "Deliver to" city presets
            'Burger Barn':   (22.2980, 73.1720),
            'Wok Express':   (22.3200, 73.1650),
            'Sweet Spot':    (22.3050, 73.1560),
            'Desi Kitchen':  (22.2900, 73.2050),
        }
        for name, (lat, lon) in coords.items():
            r = restaurants[name]
            if r.latitude is None:
                r.latitude, r.longitude = lat, lon
                r.save(update_fields=['latitude', 'longitude'])

        User = get_user_model()
        owner, created = User.objects.get_or_create(
            username='pizza_owner',
            defaults={'email': 'owner@quickbite.com', 'role': 'owner',
                      'first_name': 'Paolo', 'last_name': 'Verdi'})
        if created:
            owner.set_password('owner123')
            owner.save()
        if restaurants['Pizza Palace'].owner_id is None:
            restaurants['Pizza Palace'].owner = owner
            restaurants['Pizza Palace'].save(update_fields=['owner'])

        reviewers = [('ravi', 'Ravi', 'Patel'), ('meera', 'Meera', 'Shah'),
                     ('arjun', 'Arjun', 'Nair')]
        rusers = []
        for uname, fn, ln in reviewers:
            u, created = User.objects.get_or_create(
                username=uname,
                defaults={'first_name': fn, 'last_name': ln,
                          'email': f'{uname}@test.com', 'role': 'customer'})
            if created:
                u.set_password('test12345')
                u.save()
            rusers.append(u)

        review_data = [
            ('Margherita Pizza', 5, 'The cheese pull is unreal — best pizza in town!'),
            ('Margherita Pizza', 4, 'Fresh and hot. Base could be a bit crispier.'),
            ('Classic Smash Burger', 5, 'Juicy double patty, the sauce is addictive.'),
            ('Hyderabadi Biryani', 5, 'Perfectly dum-cooked. Meat was melt-in-mouth.'),
            ('Chocolate Donuts', 4, 'Soft, fresh glaze. Wish they had more flavors.'),
            ('Hakka Noodles', 4, 'Good wok flavor, generous veggies.'),
            ('Special Thali', 5, 'Tastes exactly like home food. Great value!'),
        ]
        for i, (dish_name, rating, comment) in enumerate(review_data):
            dish = Dish.objects.filter(name=dish_name).first()
            if dish:
                Review.objects.get_or_create(
                    user=rusers[i % len(rusers)], dish=dish,
                    defaults={'rating': rating, 'comment': comment, 'is_approved': True})
        Review.objects.get_or_create(
            user=rusers[0], restaurant=restaurants['Pizza Palace'],
            defaults={'rating': 5, 'comment': 'Quick delivery and piping-hot food!'})
        self.stdout.write(f'Reviews: {Review.objects.count()}')

        self.stdout.write(self.style.SUCCESS(
            '\n✔ Seed complete! Open /admin/ and log in to browse the data.'))
