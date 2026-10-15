"""Django settings for Givlah.

Local-prototype defaults. Configure with environment variables:
GIVLAH_SECRET_KEY, GIVLAH_DEBUG, GIVLAH_ALLOWED_HOSTS, GIVLAH_DEMO_MODE,
GIVLAH_SECURE_COOKIES, GIVLAH_DATA_DIR.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_flag(name, default=False):
    return os.environ.get(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


DEBUG = env_flag("GIVLAH_DEBUG", default=True)
SECRET_KEY = os.environ.get("GIVLAH_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("GIVLAH_SECRET_KEY must be set when GIVLAH_DEBUG is off")
    SECRET_KEY = "insecure-local-development-key"

ALLOWED_HOSTS = [h for h in os.environ.get("GIVLAH_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

# Demo mode enables labelled synthetic-account switching. Never enable it with real users.
DEMO_MODE = env_flag("GIVLAH_DEMO_MODE")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.listings",
    "apps.pwa",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "givlah.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.givlah",
            ],
        },
    },
]

WSGI_APPLICATION = "givlah.wsgi.application"

DATA_DIR = Path(os.environ.get("GIVLAH_DATA_DIR", BASE_DIR))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        # Serialize writers at BEGIN; wait at most 5 s for the write lock.
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 5},
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "listings:nearby"
LOGOUT_REDIRECT_URL = "accounts:login"

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Only sanitized images are stored here; they are served through a permission-checked view.
MEDIA_ROOT = DATA_DIR / "media"

DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_COOKIES = env_flag("GIVLAH_SECURE_COOKIES", default=not DEBUG)
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
