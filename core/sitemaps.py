from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Category, Dish, Restaurant


class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = 'daily'

    def items(self):
        return ['core:home', 'core:menu', 'core:restaurants', 'core:search',
                'core:about', 'core:contact', 'core:faq',
                'core:terms', 'core:privacy', 'core:refund']

    def location(self, item):
        return reverse(item)


class DishSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return Dish.objects.filter(
            is_available=True, restaurant__is_active=True, category__is_active=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class RestaurantSitemap(Sitemap):
    priority = 0.9
    changefreq = 'weekly'

    def items(self):
        return Restaurant.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class CategorySitemap(Sitemap):
    priority = 0.6
    changefreq = 'monthly'

    def items(self):
        return Category.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return f'{reverse("core:menu")}?category={obj.slug}'
