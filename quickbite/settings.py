"""
Django settings for QuickBite.

Environment-driven via python-decouple: every secret and deployment knob
comes from the environment (a .env file in development, real environment
variables on Render / PythonAnywhere / Railway). See .env.example.
"""

from pathlib import Path

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------- core ----------
# SECURITY WARNING: keep the secret key used in production secret!
# Dev falls back to an insecure key ONLY when DEBUG is on.
DEBUG = config('QUICKBITE_DEBUG', default=True, cast=bool)

SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-qwcd690b47+co4*hcazarfh5gksy-+5(3w--%_g!gom54q3ezb' if DEBUG else None,
)
if not SECRET_KEY:
    raise RuntimeError('SECRET_KEY must be set in the environment when DEBUG is off.')

# '*' only in dev so the sandboxed live-preview host can reach runserver.
# Production: comma-separated real domains, e.g. ALLOWED_HOSTS=quickbite.onrender.com
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='*' if DEBUG else 'localhost,127.0.0.1',
    cast=Csv(),
)

# Render and friends terminate TLS at the proxy — trust it so redirects/cookies
# are treated as HTTPS.
USE_X_FORWARDED_HOST = config('USE_X_FORWARDED_HOST', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ---------- apps ----------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',

    # ---- QuickBite apps ----
    'core',
    'accounts',
    'cart',
    'orders',
    'reviews',
    'dashboard',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # static files, gzip/brotli, cache headers
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'cart.middleware.EnsureCsrfCookieMiddleware',  # guests need the csrftoken cookie for cart AJAX
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Django Debug Toolbar — dev only (and only when explicitly enabled)
DEBUG_TOOLBAR = DEBUG and config('DEBUG_TOOLBAR', default=False, cast=bool)
if DEBUG_TOOLBAR:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']

ROOT_URLCONF = 'quickbite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart_data',        # cart badge + wishlist state
                'core.context_processors.delivery_location',  # "Deliver to" chip
                'core.context_processors.seo_defaults',      # site-wide meta/OG defaults
            ],
            'builtins': ['core.templatetags.static_min'],    # {% static_min %} — minified in prod
        },
    },
]

WSGI_APPLICATION = 'quickbite.wsgi.application'

# ---------- database ----------
# DATABASE_URL=postgres://user:pass@host:5432/dbname  → PostgreSQL (production)
# anything else (or unset)                            → local SQLite (development)
DATABASE_URL = config('DATABASE_URL', default='')
if DATABASE_URL:
    import re
    m = re.match(r'postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)', DATABASE_URL)
    if not m:
        raise RuntimeError('DATABASE_URL must look like postgres://user:pass@host:port/db')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': m.group(5),
            'USER': m.group(1),
            'PASSWORD': m.group(2),
            'HOST': m.group(3),
            'PORT': m.group(4) or '5432',
            'CONN_MAX_AGE': 60,  # persistent connections
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ---------- password validation ----------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------- i18n ----------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ---------- static & media ----------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Production: WhiteNoise fingerprints + compresses (gzip/brotli) every static file.
if DEBUG:
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
else:
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }
WHITENOISE_MAX_AGE = 30 * 24 * 3600  # 30-day cache for fingerprinted assets

# ---------- auth ----------
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'core:home'

# Simple login rate limiting (accounts/views.py): failures allowed per window.
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 10 * 60  # seconds

# ---------- email ----------
# Django 6.1+ MAILERS API. Dev prints to the console; production reads SMTP creds
# from the environment (any transactional provider works — plug in Brevo /
# SendGrid / Mailgun SMTP). NOTE: legacy EMAIL_* module settings are NOT allowed
# alongside MAILERS, so everything lives inside the MAILERS dict.
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='QuickBite <no-reply@quickbite.com>')
_email_host = config('EMAIL_HOST', default='')
if _email_host:
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
            'HOST': _email_host,
            'PORT': config('EMAIL_PORT', default=587, cast=int),
            'USERNAME': config('EMAIL_HOST_USER', default=''),
            'PASSWORD': config('EMAIL_HOST_PASSWORD', default=''),
            'USE_TLS': config('EMAIL_USE_TLS', default=True, cast=bool),
        },
    }
else:
    MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.console.EmailBackend'}}

# Contact-form recipient
CONTACT_EMAIL = config('CONTACT_EMAIL', default='hello@quickbite.com')

# ---------- SEO / analytics ----------
SITE_NAME = 'QuickBite'
SITE_TAGLINE = 'Food Delivery Made Easy'
SITE_URL = config('SITE_URL', default='http://localhost:8000')  # https://your-app.onrender.com
GA_MEASUREMENT_ID = config('GA_MEASUREMENT_ID', default='')  # G-XXXXXXXXXX
SEARCH_CONSOLE_TOKEN = config('SEARCH_CONSOLE_TOKEN', default='')  # meta-tag verification

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------- security (production) ----------
if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days — raise once HTTPS is proven
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

# ---------- cache (used by login rate limiting) ----------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'quickbite',
    }
}

# ---------- logging ----------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'simple': {'format': '[{levelname}] {name}: {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'}},
    'root': {'handlers': ['console'], 'level': config('LOG_LEVEL', default='INFO')},
}
