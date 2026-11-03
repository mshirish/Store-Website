from pathlib import Path
import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
    # Comma-separated full origins (scheme+host) trusted for CSRF form POSTs.
    # Must include the ALB DNS URL when running behind a load balancer.
    CSRF_TRUSTED_ORIGINS=(list, ['http://localhost']),
    # Reverse-proxy / HTTPS gate — all OFF by default for HTTP deployments.
    USE_X_FORWARDED_HOST=(bool, False),
    SECURE_SSL_REDIRECT=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
)
environ.Env.read_env(BASE_DIR / '.env')

# ── Core ─────────────────────────────────────────────────────────────────────
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')
# Full scheme+host origins allowed to POST forms through a reverse proxy (ALB).
# Comma-separated, e.g. http://<alb-dns-name>,http://localhost:8000
CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS')

# ── Reverse-proxy / HTTPS ─────────────────────────────────────────────────────
# Set USE_X_FORWARDED_HOST=true when behind an ALB/nginx so Django uses the
# X-Forwarded-Host header for correct URL generation and redirects.
USE_X_FORWARDED_HOST = env('USE_X_FORWARDED_HOST')

# HTTPS_PROXY=true activates SECURE_PROXY_SSL_HEADER so Django trusts the
# ALB's X-Forwarded-Proto: https header. Leave UNSET (or false) for an
# HTTP-only lab — enabling it over plain HTTP breaks session/CSRF cookies.
if env.bool('HTTPS_PROXY', default=False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Env-gated so the same image works for the HTTP lab (all False) and a future
# HTTPS deployment (set these to true in env alongside HTTPS_PROXY=true).
SECURE_SSL_REDIRECT = env('SECURE_SSL_REDIRECT')
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE')
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE')

# ── Applications ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # Third-party
    'allauth',
    'allauth.account',
    # Local
    'apps.accounts.apps.AccountsConfig',
    'apps.catalog.apps.CatalogConfig',
    'apps.core.apps.CoreConfig',
    'apps.orders.apps.OrdersConfig',
    'apps.cart.apps.CartConfig',
]

MIDDLEWARE = [
    # First: ALB health checks must bypass host validation and the database.
    'apps.core.middleware.HealthCheckMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
                'apps.cart.context_processors.cart_count',
                'apps.core.context_processors.site_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Database ─────────────────────────────────────────────────────────────────
DATABASES = {
    'default': env.db('DATABASE_URL'),
}

# ── Auth ─────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ── django-allauth ────────────────────────────────────────────────────────────
SITE_ID = 1

ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = env('ACCOUNT_EMAIL_VERIFICATION', default='mandatory')
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/'

# ── Email ─────────────────────────────────────────────────────────────────────
_email_host = env('EMAIL_HOST', default='')
if _email_host:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = _email_host
    EMAIL_PORT = env.int('EMAIL_PORT', default=587)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
    EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Order emails use the SiteConfiguration store name as the sender name; only the
# address part of this setting is used for them. allauth emails use it as-is.
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@example.com')

# ── Stripe ────────────────────────────────────────────────────────────────────
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

# ── Static & media ───────────────────────────────────────────────────────────
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
# Directory where `collectstatic` writes files for production serving.
# runserver ignores STATIC_ROOT; gunicorn (prod) needs it.
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    # Media: local filesystem under MEDIA_ROOT; swapped for R2 below when configured.
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    # WhiteNoise: serve compressed + fingerprinted static files in production.
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Media on Cloudflare R2 (optional) ────────────────────────────────────────
# When the R2 bucket and keys are set, uploads go to R2 and .url points at the
# bucket's public URL. Otherwise media stays on the local filesystem above.
# Static files are unaffected and always served by WhiteNoise.
R2_ACCESS_KEY_ID = env('R2_ACCESS_KEY_ID', default='')
R2_SECRET_ACCESS_KEY = env('R2_SECRET_ACCESS_KEY', default='')
R2_BUCKET_NAME = env('R2_BUCKET_NAME', default='')
R2_ENDPOINT_URL = env('R2_ENDPOINT_URL', default='')
R2_PUBLIC_URL = env('R2_PUBLIC_URL', default='')

USE_R2 = bool(R2_BUCKET_NAME and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY)

if USE_R2:
    # Fail at startup rather than uploading somewhere unreachable.
    if not (R2_ENDPOINT_URL and R2_PUBLIC_URL):
        raise ImproperlyConfigured(
            'R2_ENDPOINT_URL and R2_PUBLIC_URL must be set when R2 media storage is enabled.'
        )
    # S3Storage is django-storages' boto3 backend (S3Boto3Storage is its legacy alias).
    STORAGES['default'] = {'BACKEND': 'storages.backends.s3.S3Storage'}
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = R2_ENDPOINT_URL
    AWS_S3_REGION_NAME = 'auto'          # R2 requires "auto"
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_DEFAULT_ACL = None               # R2 rejects ACL headers
    AWS_QUERYSTRING_AUTH = False         # public, unsigned URLs
    # Host (and optional path) only, e.g. pub-xxxx.r2.dev
    AWS_S3_CUSTOM_DOMAIN = R2_PUBLIC_URL.split('://', 1)[-1].rstrip('/')
    AWS_S3_FILE_OVERWRITE = False

# ── Misc ──────────────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
