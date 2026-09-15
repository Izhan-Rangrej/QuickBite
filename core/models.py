import math
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    """Abstract base: every table gets created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    """Food category — Pizza, Burger, Biryani, Sushi, ..."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Restaurant(TimeStampedModel):
    """A restaurant that sells dishes."""

    CUISINE_CHOICES = [
        ('pizza', 'Pizza'),
        ('burger', 'Burger'),
        ('indian', 'Indian'),
        ('chinese', 'Chinese'),
        ('dessert', 'Dessert'),
        ('sushi', 'Sushi'),
        ('thali', 'Thali'),
        ('rolls', 'Rolls'),
        ('multi', 'Multi-Cuisine'),
    ]

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    image = models.ImageField(upload_to='restaurants/', blank=True, null=True)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    cuisine_type = models.CharField(max_length=20, choices=CUISINE_CHOICES, default='multi')
    rating = models.DecimalField(
        max_digits=2, decimal_places=1, default=4.0,
        validators=[MinValueValidator(Decimal('0.0')), MaxValueValidator(Decimal('5.0'))],
        help_text='0.0 – 5.0',
    )
    delivery_time = models.PositiveIntegerField(help_text='Average delivery time in minutes', default=30)
    min_order = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    offer_text = models.CharField(
        max_length=100, blank=True,
        help_text='Offer banner shown on the card, e.g. "40% OFF up to ₹80"',
    )
    is_promoted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    opening_time = models.TimeField(default=None, null=True, blank=True)
    closing_time = models.TimeField(default=None, null=True, blank=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='owned_restaurants',
        help_text='Restaurant owner with access to the owner panel',
    )

    class Meta:
        ordering = ['-is_promoted', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('core:restaurant_detail', args=[self.slug])

    @property
    def is_open_now(self):
        """True when the current local time falls inside opening/closing hours."""
        if not self.opening_time or not self.closing_time:
            return True  # hours not set — assume open
        now = timezone.localtime().time()
        if self.opening_time <= self.closing_time:            # e.g. 10:00 – 23:00
            return self.opening_time <= now <= self.closing_time
        return now >= self.opening_time or now <= self.closing_time  # crosses midnight

    # ---- location helpers ----

    MAX_DELIVERY_KM = 15.0

    def distance_km_from(self, lat, lon):
        """Haversine distance in km, or None when either side has no coords."""
        if None in (self.latitude, self.longitude, lat, lon):
            return None
        r = 6371.0
        p1, p2 = math.radians(self.latitude), math.radians(lat)
        dp = p2 - p1
        dl = math.radians(lon - self.longitude)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return round(r * 2 * math.asin(math.sqrt(a)), 1)

    def delivery_extra_minutes(self, distance_km):
        """+5 min for every 5 km beyond the first 5 km (capped at +25)."""
        if distance_km is None:
            return 0
        return min(25, max(0, math.ceil((distance_km - 5) / 5)) * 5)

    def location_context(self, lat, lon):
        """{'distance_km', 'eta_minutes', 'delivers'} for the current user location."""
        distance = self.distance_km_from(lat, lon)
        if distance is None:
            return {'distance_km': None, 'eta_minutes': self.delivery_time,
                    'delivers': True}
        delivers = distance <= self.MAX_DELIVERY_KM
        extra = self.delivery_extra_minutes(distance) if delivers else 0
        return {'distance_km': distance,
                'eta_minutes': self.delivery_time + extra,
                'delivers': delivers}


class Dish(TimeStampedModel):
    """A single menu item belonging to one restaurant and one category."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='dishes/', blank=True, null=True)
    price = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    discount_price = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Leave blank if not discounted',
    )
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='dishes')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='dishes')
    is_bestseller = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    is_veg = models.BooleanField(default=True)
    rating = models.DecimalField(
        max_digits=2, decimal_places=1, default=4.0,
        validators=[MinValueValidator(Decimal('0.0')), MaxValueValidator(Decimal('5.0'))],
    )
    preparation_time = models.PositiveIntegerField(help_text='Minutes', default=20)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['-is_bestseller', 'name']
        verbose_name_plural = 'Dishes'

    def __str__(self):
        return f'{self.name} — {self.restaurant.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            n = 2
            # keep slugs unique across restaurants (two places can sell "Veg Pizza")
            while Dish.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('core:dish_detail', args=[self.slug])

    @property
    def effective_price(self):
        """Price the customer actually pays."""
        return self.discount_price if self.discount_price is not None else self.price

    @property
    def discount_percent(self):
        """e.g. 43 for ₹349 → ₹199."""
        if self.discount_price is None or self.price <= 0:
            return 0
        return int(((self.price - self.discount_price) / self.price * 100).quantize(Decimal('1')))


class Coupon(TimeStampedModel):
    """Discount coupon / offer code (FIRST50, FREEDEL, ...)."""

    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))],
        help_text='Set EITHER percentage OR flat amount',
    )
    discount_amount = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Flat ₹ off — set EITHER amount OR percentage',
    )
    min_order_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    max_discount = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True,
        help_text='Cap for percentage coupons, e.g. "50% up to ₹100"',
    )
    usage_limit = models.PositiveIntegerField(
        blank=True, null=True,
        help_text='Total redemptions allowed (blank = unlimited)',
    )
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.title}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.discount_percentage is None and self.discount_amount is None:
            raise ValidationError('Set either discount_percentage or discount_amount.')
        if self.discount_percentage is not None and self.discount_amount is not None:
            raise ValidationError('Set only ONE of discount_percentage / discount_amount, not both.')
        if self.valid_until and self.valid_from and self.valid_until < self.valid_from:
            raise ValidationError('valid_until must be after valid_from.')

    @property
    def is_valid_now(self):
        now = timezone.now()
        within_dates = self.is_active and self.valid_from <= now <= self.valid_until
        within_usage = self.usage_limit is None or self.used_count < self.usage_limit
        return within_dates and within_usage

    @property
    def discount_display(self):
        if self.discount_percentage:
            return f'{float(self.discount_percentage):g}% OFF'
        return f'FLAT ₹{float(self.discount_amount):g} OFF'

    def get_discount_value(self, order_total):
        """Actual ₹ discount for a given order total (respects min order + cap)."""
        if not self.is_valid_now or order_total < self.min_order_amount:
            return Decimal('0.00')
        if self.discount_percentage:
            discount = (order_total * self.discount_percentage / Decimal('100')).quantize(Decimal('0.01'))
            if self.max_discount:
                discount = min(discount, self.max_discount)
        else:
            discount = self.discount_amount
        return min(discount, order_total)
