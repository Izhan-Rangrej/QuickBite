import json
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from reviews.models import Review, avg_rating

from .models import Category, Coupon, Dish, Restaurant


# ---------- helpers ----------

def _available_dishes():
    """Base queryset: dishes that may be shown to customers."""
    return (
        Dish.objects
        .filter(is_available=True, restaurant__is_active=True, category__is_active=True)
        .select_related('restaurant', 'category')
    )


def _querystring(request, exclude=('page',)):
    """Current GET params as a querystring, minus `exclude` keys (for pagination links)."""
    params = request.GET.copy()
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


def _paginate(request, queryset, per_page):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def _decimal_or_none(value):
    try:
        return Decimal(value) if value not in ('', None) else None
    except (InvalidOperation, ValueError):
        return None


def _user_coords(request):
    lat, lon = request.session.get('delivery_lat'), request.session.get('delivery_lon')
    return (lat, lon) if lat is not None and lon is not None else (None, None)


def _attach_locations(restaurants, request):
    """Set `.loc` (distance/eta/delivers) on each restaurant when the user
    has a delivery location. Templates read `restaurant.loc`."""
    lat, lon = _user_coords(request)
    for r in restaurants:
        r.loc = r.location_context(lat, lon) if lat is not None else None
    return restaurants


def _review_context(target_kind, target, user):
    """Reviews + rating breakdown for a dish or restaurant page."""
    qs = (target.reviews.filter(is_approved=True)
          .select_related('user').prefetch_related('helpful_users'))
    average, count = avg_rating(target.reviews)
    breakdown = []
    for star in range(5, 0, -1):
        n = sum(1 for r in qs if r.rating == star)
        breakdown.append({'star': star, 'count': n,
                          'pct': round(n * 100 / count) if count else 0})
    user_review = None
    review_order_id = None
    can_review = False
    if user.is_authenticated:
        user_review = Review.objects.filter(
            user=user,
            dish=target if target_kind == 'dish' else None,
            restaurant=target if target_kind == 'restaurant' else None,
        ).first()
        if user_review is None:
            if target_kind == 'dish':
                # dishes: verified reviews only — a delivered order containing
                # this dish unlocks the form (spec: review after delivery)
                from orders.models import Order
                delivered = Order.objects.filter(
                    user=user, status=Order.Status.DELIVERED,
                    items__dish=target).order_by('-created_at').first()
                can_review = delivered is not None
                review_order_id = delivered.order_id if delivered else None
            else:
                can_review = True  # restaurants: any logged-in customer
    return {'reviews': qs, 'avg_rating': average, 'review_count': count,
            'rating_breakdown': breakdown, 'user_review': user_review,
            'can_review': can_review, 'review_order_id': review_order_id}


# ---------- pages ----------

def home(request):
    """Landing page — renders templates/core/home.html with live database data."""
    now = timezone.now()

    categories = Category.objects.filter(is_active=True)

    # "Popular" = bestsellers first, then top-rated; 6 per page like the template grid
    popular_qs = _available_dishes().order_by('-is_bestseller', '-rating', 'name')
    page_obj = _paginate(request, popular_qs, 6)

    coupons = Coupon.objects.filter(
        is_active=True, valid_from__lte=now, valid_until__gte=now,
    ).order_by('-created_at')[:2]

    promo_images = list(
        _available_dishes().filter(is_bestseller=True)
        .exclude(image='')
        .values_list('image', flat=True)[:2]
    )
    offers = [
        {
            'coupon': coupon,
            'image': promo_images[i % len(promo_images)] if promo_images else None,
        }
        for i, coupon in enumerate(coupons)
    ]

    restaurants = _attach_locations(
        Restaurant.objects.filter(is_active=True)
        .order_by('-is_promoted', '-rating', 'name')[:4], request)

    return render(request, 'core/home.html', {
        'categories': categories,
        'page_obj': page_obj,
        'offers': offers,
        'restaurants': restaurants,
    })


def _filter_dishes(request, qs):
    """Apply all menu-page filters. Returns (qs, state_dict)."""
    qs = qs.annotate(eff_price=Coalesce('discount_price', 'price'))

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(restaurant__name__icontains=q)
        )

    category = request.GET.get('category', '').strip()
    if category:
        qs = qs.filter(category__slug=category)

    veg = request.GET.get('veg', '').strip()
    if veg == '1':
        qs = qs.filter(is_veg=True)
    elif veg == '0':
        qs = qs.filter(is_veg=False)

    min_price = _decimal_or_none(request.GET.get('min_price', '').strip())
    max_price = _decimal_or_none(request.GET.get('max_price', '').strip())
    if min_price is not None:
        qs = qs.filter(eff_price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(eff_price__lte=max_price)

    rating = _decimal_or_none(request.GET.get('rating', '').strip())
    if rating is not None:
        qs = qs.filter(rating__gte=rating)

    delivery = request.GET.get('delivery', '').strip()
    if delivery.isdigit():
        qs = qs.filter(restaurant__delivery_time__lte=int(delivery))

    cuisines = [c for c in request.GET.get('cuisines', '').split(',') if c]
    if cuisines:
        qs = qs.filter(restaurant__cuisine_type__in=cuisines)

    sort = request.GET.get('sort', 'relevance' if q else 'popular')
    if sort == 'relevance' and q:
        # exact hits first, then starts-with, then contains
        qs = qs.annotate(relevance=Case(
            When(name__iexact=q, then=Value(0)),
            When(name__istartswith=q, then=Value(1)),
            default=Value(2), output_field=IntegerField(),
        )).order_by('relevance', '-is_bestseller', '-rating', 'name')
    else:
        sort_map = {
            'popular': ('-is_bestseller', '-rating', 'name'),
            'price_asc': ('eff_price', 'name'),
            'price_desc': ('-eff_price', 'name'),
            'rating': ('-rating', 'name'),
            'delivery': ('restaurant__delivery_time', 'name'),
        }
        qs = qs.order_by(*sort_map.get(sort, sort_map['popular']))

    state = {
        'q': q, 'category': category, 'veg': veg, 'sort': sort,
        'min_price': request.GET.get('min_price', ''),
        'max_price': request.GET.get('max_price', ''),
        'rating': request.GET.get('rating', ''),
        'delivery': delivery,
        'cuisines': cuisines,
    }
    return qs, state


def _menu_context(request):
    categories = (
        Category.objects.filter(is_active=True)
        .annotate(active_dishes=Count(
            'dishes',
            filter=Q(dishes__is_available=True, dishes__restaurant__is_active=True),
        ))
    )
    qs, state = _filter_dishes(request, _available_dishes())
    return {
        'categories': categories,
        'page_obj': _paginate(request, qs, 9),
        'base_qs': _querystring(request),
        'qs_no_category': _querystring(request, exclude=('page', 'category')),
        'total_results': qs.count(),
        'cuisine_choices': Restaurant.CUISINE_CHOICES,
        **state,
    }


def menu(request):
    """All dishes — advanced filters. `?ajax=1` returns just the results
    partial (grid + active filter tags + pagination) for filters.js."""
    ctx = _menu_context(request)
    if request.GET.get('ajax') == '1':
        return render(request, 'core/includes/menu_results.html', ctx)
    return render(request, 'core/menu.html', ctx)


def _filter_restaurants(request, qs):
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(address__icontains=q)
        )

    cuisine = request.GET.get('cuisine', '').strip()
    if cuisine:
        qs = qs.filter(cuisine_type=cuisine)

    rating = _decimal_or_none(request.GET.get('rating', '').strip())
    if rating is not None:
        qs = qs.filter(rating__gte=rating)

    delivery = request.GET.get('delivery', '').strip()
    if delivery.isdigit():
        qs = qs.filter(delivery_time__lte=int(delivery))

    veg = request.GET.get('veg', '').strip()
    if veg in ('1', '0'):
        qs = qs.filter(dishes__is_veg=(veg == '1')).distinct()

    sort = request.GET.get('sort', 'popular')
    sort_map = {
        'popular': ('-is_promoted', '-rating', 'name'),
        'rating': ('-rating', 'name'),
        'delivery': ('delivery_time', 'name'),
        'distance': ('-is_promoted', '-rating', 'name'),  # refined post-query
    }
    qs = qs.order_by(*sort_map.get(sort, sort_map['popular']))

    state = {'q': q, 'cuisine': cuisine, 'sort': sort,
             'rating': request.GET.get('rating', ''), 'delivery': delivery, 'veg': veg}
    return qs, state


def _restaurant_list_context(request):
    qs, state = _filter_restaurants(request, Restaurant.objects.filter(is_active=True))
    lat, lon = _user_coords(request)
    page_obj = _paginate(request, qs, 9)
    _attach_locations(list(page_obj), request)
    if lat is not None and state['sort'] == 'distance':
        page_obj.object_list = sorted(
            page_obj.object_list,
            key=lambda r: (r.loc['distance_km'] is None, r.loc['distance_km'] or 0))
    return {
        'page_obj': page_obj,
        'base_qs': _querystring(request),
        'cuisine_choices': Restaurant.CUISINE_CHOICES,
        'total_results': qs.count(),
        'has_location': lat is not None,
        **state,
    }


def restaurant_list(request):
    """All restaurants with search + filters + sort (AJAX partial supported)."""
    ctx = _restaurant_list_context(request)
    if request.GET.get('ajax') == '1':
        return render(request, 'core/includes/restaurant_results.html', ctx)
    return render(request, 'core/restaurants.html', ctx)


def restaurant_detail(request, slug):
    """Restaurant hero + info + full menu grouped by category + reviews."""
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    dishes = (
        restaurant.dishes
        .filter(is_available=True, category__is_active=True)
        .select_related('category')
        .order_by('category__name', '-is_bestseller', 'name')
    )
    lat, lon = _user_coords(request)
    loc = restaurant.location_context(lat, lon) if lat is not None else None
    return render(request, 'core/restaurant_detail.html', {
        'restaurant': restaurant,
        'dishes': dishes,
        'loc': loc,
        **_review_context('restaurant', restaurant, request.user),
    })


def dish_detail(request, slug):
    """Dish page: image, info, quantity selector, similar dishes, reviews."""
    dish = get_object_or_404(
        _available_dishes(), slug=slug,
    )
    similar = (
        _available_dishes()
        .filter(category=dish.category)
        .exclude(pk=dish.pk)
        .order_by('-is_bestseller', '-rating')[:3]
    )
    return render(request, 'core/dish_detail.html', {
        'dish': dish,
        'similar_dishes': similar,
        **_review_context('dish', dish, request.user),
    })


# ---------- global search ----------

def search(request):
    """Search results page — mixed sections for dishes / restaurants / categories."""
    q = request.GET.get('q', '').strip()
    dishes = restaurants = categories = None
    if q:
        dishes = _available_dishes().filter(
            Q(name__icontains=q) | Q(description__icontains=q) |
            Q(restaurant__name__icontains=q))[:12]
        restaurants = Restaurant.objects.filter(is_active=True).filter(
            Q(name__icontains=q) | Q(description__icontains=q) |
            Q(cuisine_type__icontains=q) | Q(address__icontains=q))[:6]
        categories = Category.objects.filter(is_active=True, name__icontains=q)[:6]
        _attach_locations(list(restaurants), request)

    total = sum(len(x) for x in (dishes, restaurants, categories) if x is not None)
    return render(request, 'core/search_results.html', {
        'q': q,
        'dishes': dishes, 'restaurants': restaurants, 'categories': categories,
        'total': total,
        # "no results" helpers
        'suggested_categories': Category.objects.filter(is_active=True)[:6],
        'popular_dishes': _available_dishes().order_by('-is_bestseller', '-rating')[:4],
    })


def search_suggest(request):
    """Navbar autocomplete — mixed top-8 JSON."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'q': q, 'results': [], 'total': 0})

    results = []
    for d in _available_dishes().filter(name__icontains=q)[:5]:
        price = d.effective_price
        price = price.quantize(Decimal('1')) if price == price.to_integral_value() \
            else price.quantize(Decimal('0.01'))
        results.append({
            'type': 'dish', 'name': d.name,
            'sub': f'{d.restaurant.name} · {d.category.name}',
            'price': f'₹{price}',
            'image': d.image.url if d.image else None,
            'url': d.get_absolute_url(),
        })
    for r in Restaurant.objects.filter(is_active=True, name__icontains=q)[:2]:
        results.append({
            'type': 'restaurant', 'name': r.name,
            'sub': f'{r.get_cuisine_type_display()} · {r.address}',
            'price': None, 'image': r.image.url if r.image else None,
            'url': r.get_absolute_url(),
        })
    for c in Category.objects.filter(is_active=True, name__icontains=q)[:2]:
        results.append({
            'type': 'category', 'name': c.name,
            'sub': 'Category', 'price': None,
            'image': c.image.url if c.image else None,
            'url': f'/menu/?category={c.slug}',
        })
    return JsonResponse({'q': q, 'results': results[:8], 'total': len(results)})


# ---------- delivery location ----------

CITY_COORDS = {
    'vadodara': (22.3072, 73.1812),
    'ahmedabad': (23.0225, 72.5714),
    'surat': (21.1702, 72.8311),
    'mumbai': (19.0760, 72.8777),
    'delhi': (28.6139, 77.2090),
    'bengaluru': (12.9716, 77.5946),
}


def _any_restaurant_in_range(lat, lon):
    for r in Restaurant.objects.filter(is_active=True).exclude(latitude=None):
        d = r.distance_km_from(lat, lon)
        if d is not None and d <= r.MAX_DELIVERY_KM:
            return True
    return False


@require_POST
def location_set(request):
    """Store the delivery location in the session (browser geolocation or a city pick)."""
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = request.POST
    lat, lon = body.get('lat'), body.get('lon')
    label = (body.get('label') or '').strip()[:60]
    city_key = (body.get('city') or '').strip().lower()

    if lat is None or lon is None:
        if city_key in CITY_COORDS:
            lat, lon = CITY_COORDS[city_key]
            label = label or city_key.title()
        else:
            return JsonResponse({'ok': False, 'message': 'Missing coordinates.'}, status=400)

    request.session['delivery_lat'] = float(lat)
    request.session['delivery_lon'] = float(lon)
    request.session['delivery_label'] = label or 'Current Location'
    request.session.modified = True
    return JsonResponse({
        'ok': True,
        'label': request.session['delivery_label'],
        'delivers': _any_restaurant_in_range(float(lat), float(lon)),
        'message': (f'🎉 We deliver to {request.session["delivery_label"]}!'
                    if _any_restaurant_in_range(float(lat), float(lon))
                    else f'Sorry, QuickBite is not live in {request.session["delivery_label"]} yet.'),
    })


@require_POST
def location_clear(request):
    for key in ('delivery_lat', 'delivery_lon', 'delivery_label'):
        request.session.pop(key, None)
    return redirect(request.POST.get('next') or 'core:home')


# ---------- SEO ----------

def robots_txt(request):
    """Disallow the private areas, point crawlers at the sitemap."""
    body = '\n'.join([
        'User-agent: *',
        'Allow: /$',
        'Allow: /menu/',
        'Allow: /restaurants/',
        'Allow: /restaurant/',
        'Allow: /dish/',
        'Allow: /search/',
        'Allow: /about/',
        'Allow: /faq/',
        'Disallow: /admin/',
        'Disallow: /dashboard/',
        'Disallow: /panel/',
        'Disallow: /accounts/',
        'Disallow: /cart/',
        'Disallow: /checkout/',
        'Disallow: /orders/',
        'Disallow: /location/',
        '',
        f'Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml',
    ])
    return HttpResponse(body, content_type='text/plain')


# ---------- informational pages (Phase 10) ----------

def about(request):
    from .models import Restaurant as _R
    return render(request, 'core/pages/about.html', {
        'restaurant_count': _R.objects.filter(is_active=True).count(),
        'dish_count': _available_dishes().count(),
    })


def contact(request):
    from django.core.mail import send_mail

    from .forms import ContactForm
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            send_mail(
                subject=f'[QuickBite contact] {data["subject"]}: {data["name"]}',
                message=(f'From: {data["name"]} <{data["email"]}>\n'
                         f'Phone: {data.get("phone") or "not provided"}\n\n'
                         f'{data["message"]}'),
                from_email=None,
                recipient_list=[settings.CONTACT_EMAIL],
                fail_silently=True,
            )
            messages.success(request, 'Thanks for writing in — we reply within 24 hours! 💌')
            return redirect('core:contact')
    else:
        form = ContactForm(initial={'email': request.user.email}
                           if request.user.is_authenticated else {})
    return render(request, 'core/pages/contact.html', {'form': form})


FAQS = [
    ('Ordering', [
        ('How do I place an order?',
         'Browse the menu or search for a dish, add it to your cart, then head to '
         'checkout. Pick a delivery address, choose Cash on Delivery, and hit "Place '
         'Order" — that\'s it!'),
        ('Can I order from multiple restaurants at once?',
         'Yes! Your cart can hold dishes from different restaurants. Keep in mind '
         'each restaurant prepares independently, so the delivery ETA reflects the '
         'slowest kitchen in your cart.'),
        ('What payment methods do you accept?',
         'Cash on Delivery is live today. UPI, cards and wallets are coming soon — '
         'you can already see them at checkout.'),
    ]),
    ('Delivery', [
        ('How is the delivery time calculated?',
         'ETA = the longest preparation time in your cart + ~10 minutes of travel. '
         'If you set a delivery location, we add travel time based on the real '
         'distance to each restaurant.'),
        ('Where do you deliver?',
         'We currently serve restaurants within a 15 km radius of your location. '
         'Use the "Deliver to" button in the navbar to check your address.'),
        ('Can I track my order?',
         'Absolutely — open My Orders and tap any order to watch it move through '
         'Confirmed → Preparing → Out for Delivery → Delivered in real time.'),
    ]),
    ('Coupons & payments', [
        ('How do I apply a coupon?',
         'On the cart or checkout page, type the code (like FIRST50) into the coupon '
         'box and hit Apply. Coupons are re-validated when you place the order.'),
        ('Why was my coupon rejected at checkout?',
         'Coupons can expire, hit a usage limit, or require a minimum cart value. If '
         'any of that happens between applying and ordering, we remove the coupon '
         'and ask you to review before placing the order — you never lose money.'),
    ]),
    ('Account', [
        ('How do I cancel an order?',
         'Orders can be cancelled free of charge until the kitchen starts preparing. '
         'Open the order and hit "Cancel this order".'),
        ('How do refunds work?',
         'Cancelled COD orders need no refund. If you ever pre-pay (once online '
         'payments launch), refunds land back on the original payment method in '
         '5–7 working days. See our Refund Policy for details.'),
        ('Can restaurants see my reviews?',
         'Yes — reviews help partners improve. Restaurant owners see ratings and '
         'comments for their dishes in their owner panel.'),
    ]),
]


def faq(request):
    return render(request, 'core/pages/faq.html', {'faq_groups': FAQS})


def terms(request):
    return render(request, 'core/pages/terms.html')


def privacy(request):
    return render(request, 'core/pages/privacy.html')


def refund(request):
    return render(request, 'core/pages/refund.html')
