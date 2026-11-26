import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = config('DEBUG', default=False, cast=bool)

SECRET_KEY = config('SECRET_KEY', default='')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set the SECRET_KEY environment variable (it is required when DEBUG is off).')
    SECRET_KEY = 'dev-only-insecure-key-do-not-use-in-production'

ALLOWED_HOSTS = ['prophane.onrender.com', 'localhost', '127.0.0.1'] + config('EXTRA_ALLOWED_HOSTS', default='', cast=Csv())
CSRF_TRUSTED_ORIGINS = ['https://prophane.onrender.com']

# Render sets this to the service's own hostname, so a renamed service still works
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'store',
]

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'store.middleware.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'propane_exchange.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'store.context_processors.navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'propane_exchange.wsgi.application'

# On Render this is the Supabase Postgres connection string
# (Supabase dashboard > Connect > Session pooler).
DATABASE_URL = config('DATABASE_URL', default='') or config('SUPABASE_DB_URL', default='')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=60,
            conn_health_checks=True,
            ssl_require='sqlite' not in DATABASE_URL,
        )
    }
    # Supabase's transaction pooler (port 6543) can't hold server-side cursors
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Supabase Storage for uploads (photos, seller documents, pickup proofs).
# Without these, uploads go to the local media/ folder (fine for local dev).
SUPABASE_URL = config('SUPABASE_URL', default='')
SUPABASE_KEY = (
    config('SUPABASE_SERVICE_ROLE_KEY', default='')
    or config('SUPABASE_KEY', default='')
)
SUPABASE_BUCKET = config('SUPABASE_BUCKET', default='media')
USE_SUPABASE_STORAGE = bool(SUPABASE_URL and SUPABASE_KEY)

STORAGES = {
    'default': {
        'BACKEND': (
            'store.storage.SupabaseStorage' if USE_SUPABASE_STORAGE
            else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.CompressedManifestStaticFilesStorage' if not DEBUG
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

TESTING = sys.argv[1:2] == ['test']
if TESTING:
    # Tests run without collectstatic, and fast hashing keeps them quick
    STORAGES['staticfiles']['BACKEND'] = 'django.contrib.staticfiles.storage.StaticFilesStorage'
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Uploads: individual files are capped at 5 MB in the forms; these stop
# oversized requests before they reach a view.
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
FILE_UPLOAD_PERMISSIONS = 0o640

# Accounts

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
ACCOUNT_LOGOUT_REDIRECT_URL = 'login'
ACCOUNT_SIGNUP_REDIRECT_URL = 'dashboard'

ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['email', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_SESSION_REMEMBER = None  # let the user choose
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_RATE_LIMITS = {
    'login': '30/m/ip',
    'login_failed': '5/15m/key,20/15m/ip',
    'signup': '10/h/ip',
}

SOCIALACCOUNT_AUTO_SIGNUP = True
# Show a confirmation page before redirecting to Google, so a third-party
# page can't silently log someone in with a crafted link.
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_QUERY_EMAIL = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID', default=''),
            'secret': config('GOOGLE_CLIENT_SECRET', default=''),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'OAUTH_PKCE_ENABLED': True,
        'VERIFIED_EMAIL': False,
    }
}

# Sessions and cookies

SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'django.views.csrf.csrf_failure'

# HTTP security headers

X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
# Send our origin (not full URLs) to other sites. OpenStreetMap blocks map
# tile requests that arrive without a Referer.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

if not DEBUG:
    # Render terminates HTTPS and forwards plain HTTP; trust its header so
    # SECURE_SSL_REDIRECT doesn't redirect forever.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=60 * 60 * 24 * 365, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

_supabase_origin = ''
if SUPABASE_URL:
    _parsed = urlparse(SUPABASE_URL)
    _supabase_origin = f'{_parsed.scheme}://{_parsed.netloc}'

CONTENT_SECURITY_POLICY = {
    'default-src': ["'self'"],
    'script-src': ["'self'", 'https://unpkg.com/leaflet@1.9.4/'],
    'style-src': ["'self'", 'https://unpkg.com/leaflet@1.9.4/'],
    'img-src': ["'self'", 'data:', 'blob:', 'https://tile.openstreetmap.org', 'https://unpkg.com/leaflet@1.9.4/']
               + ([_supabase_origin] if _supabase_origin else []),
    'font-src': ["'self'"],
    'connect-src': ["'self'"],
    'object-src': ["'none'"],
    'base-uri': ["'self'"],
    'frame-ancestors': ["'none'"],
    'form-action': ["'self'", 'https://accounts.google.com'],
}
if not DEBUG:
    CONTENT_SECURITY_POLICY['upgrade-insecure-requests'] = []

# Django's own admin uses inline styles, so it is left out of the CSP.
ADMIN_URL = config('ADMIN_URL', default='admin/').strip('/') + '/'
CSP_EXEMPT_PATHS = ['/' + ADMIN_URL]

PERMISSIONS_POLICY = 'geolocation=(self), camera=(), microphone=(), payment=(), usb=(), interest-cohort=()'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO'},
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'allauth': {'handlers': ['console'], 'level': 'WARNING'},
    },
}
