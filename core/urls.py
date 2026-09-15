from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import sitemaps as qb_sitemaps
from . import views

app_name = 'core'

sitemaps = {
    'static': qb_sitemaps.StaticViewSitemap,
    'dishes': qb_sitemaps.DishSitemap,
    'restaurants': qb_sitemaps.RestaurantSitemap,
    'categories': qb_sitemaps.CategorySitemap,
}

urlpatterns = [
    path('', views.home, name='home'),
    path('menu/', views.menu, name='menu'),
    path('restaurants/', views.restaurant_list, name='restaurants'),
    path('restaurant/<slug:slug>/', views.restaurant_detail, name='restaurant_detail'),
    path('dish/<slug:slug>/', views.dish_detail, name='dish_detail'),

    # global search
    path('search/', views.search, name='search'),
    path('search/suggest/', views.search_suggest, name='search_suggest'),

    # delivery location
    path('location/set/', views.location_set, name='location_set'),
    path('location/clear/', views.location_clear, name='location_clear'),

    # SEO
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', views.robots_txt, name='robots_txt'),

    # informational pages (Phase 10)
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('faq/', views.faq, name='faq'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('refund-policy/', views.refund, name='refund'),
]
