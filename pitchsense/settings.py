"""
Django settings for pitchsense project.

Production-ready configuration:
- PostgreSQL via DATABASE_URL (falls back to SQLite for local dev)
- Redis channel layer via REDIS_URL (falls back to InMemory for local dev)
- Full security headers in production (HSTS, secure cookies, SSL redirect)
- Sentry error tracking (optional, via SENTRY_DSN)
- Structured logging
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# ── Secret Key ───────────────────────────────────────────────────────────
# MUST be set via environment variable in production. The fallback is ONLY
# for local development convenience and is intentionally marked insecure.

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if os.environ.get('DEBUG', 'False') == 'True':
        # Local dev only — generate a random key each restart
        from django.core.management.utils import get_random_secret_key
        SECRET_KEY = get_random_secret_key()
    else:
        raise ValueError(
            'DJANGO_SECRET_KEY environment variable is required in production. '
            'Generate one at https://djecrety.ir/'
        )


# ── Core Settings ────────────────────────────────────────────────────────

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# ── Installed Apps ───────────────────────────────────────────────────────

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'debate',
]


# ── Middleware ────────────────────────────────────────────────────────────

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ── URL & Template Config ────────────────────────────────────────────────

ROOT_URLCONF = 'pitchsense.urls'

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
            ],
        },
    },
]


# ── ASGI / WSGI ──────────────────────────────────────────────────────────

WSGI_APPLICATION = 'pitchsense.wsgi.application'
ASGI_APPLICATION = 'pitchsense.asgi.application'


# ── Channel Layers ───────────────────────────────────────────────────────
# Uses Redis in production (via REDIS_URL), falls back to InMemory for dev.

_redis_url = os.environ.get('REDIS_URL')

if _redis_url:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [_redis_url],
                'capacity': 1500,
                'expiry': 60,
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }


# ── Cache ────────────────────────────────────────────────────────────────
# Redis in production (reuses REDIS_URL), LocMem for local dev.
# Used by: rate limiter, auth check caching, Tavily research caching.

if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
            'TIMEOUT': 300,  # 5 minute default TTL
            'KEY_PREFIX': 'pitchsense',
            'OPTIONS': {
                'db': 1,  # Use DB 1 to avoid collision with channel layer on DB 0
            },
        },
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'pitchsense-dev-cache',
        },
    }


# ── Session Engine ───────────────────────────────────────────────────────
# cached_db: checks cache first, falls back to DB. Eliminates a DB query
# on every /api/auth-check/ call when cache is warm.

SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'


# ── Database ─────────────────────────────────────────────────────────────
# Uses PostgreSQL in production (via DATABASE_URL), falls back to SQLite.

import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# ── Authentication ───────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ── Session Security ─────────────────────────────────────────────────────

SESSION_COOKIE_AGE = 86400              # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True           # JS can't read session cookie
SESSION_COOKIE_SAMESITE = 'Lax'


# ── Internationalization ─────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ── Static Files ─────────────────────────────────────────────────────────

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

_frontend_build = BASE_DIR / 'frontend' / 'build'
STATICFILES_DIRS = [_frontend_build] if _frontend_build.exists() else []

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ── External API Keys ───────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY', '')


# ── Misc ─────────────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ── Production Security Headers ──────────────────────────────────────────
# Only active when DEBUG=False. Enforces HTTPS, HSTS, secure cookies.

if not DEBUG:
    # Validate critical API keys in production
    assert GROQ_API_KEY, (
        'GROQ_API_KEY environment variable is required in production. '
        'Without it, the Groq service silently returns mock responses.'
    )

    # Force HTTPS
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # HSTS: tell browsers to ONLY use HTTPS for 1 year
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Secure cookies (HTTPS-only)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Prevent clickjacking and MIME sniffing
    X_FRAME_OPTIONS = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # CSRF trusted origins (your Railway/Render domain)
    CSRF_TRUSTED_ORIGINS = [
        f'https://{host.strip()}'
        for host in ALLOWED_HOSTS
        if host.strip() not in ('localhost', '127.0.0.1', '*')
    ]


# ── Sentry Error Tracking ───────────────────────────────────────────────
# REQUIRED in production. Set SENTRY_DSN env var. Free tier: sentry.io

_sentry_dsn = os.environ.get('SENTRY_DSN')
if not DEBUG:
    if not _sentry_dsn:
        import warnings
        warnings.warn(
            'SENTRY_DSN is not set. Error tracking is DISABLED in production. '
            'Set SENTRY_DSN to enable. Get a free DSN at https://sentry.io',
            RuntimeWarning,
            stacklevel=1,
        )
    else:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=_sentry_dsn,
                traces_sample_rate=0.1,
                profiles_sample_rate=0.1,
                send_default_pii=False,
            )
        except ImportError:
            raise ImportError(
                'sentry-sdk is listed in requirements.txt but could not be imported. '
                'Run: pip install sentry-sdk'
            )


# ── Logging ──────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'debate': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
