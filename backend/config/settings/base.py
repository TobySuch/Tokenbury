import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = "placeholder-override-in-local-and-production"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "world",
    "simulation",
    "werewolf",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # must be first
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "/static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

cache_option = os.environ.get("CACHE", "locmem").lower()
if cache_option == "valkey":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": (
                f"redis://{os.environ.get('VALKEY_HOST', 'valkey')}"
                f":{os.environ.get('VALKEY_PORT', '6379')}/0"
            ),
            "KEY_PREFIX": "tokenbury",
            "OPTIONS": {"socket_connect_timeout": 0.5, "socket_timeout": 0.5},
        }
    }
elif cache_option == "locmem":
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    raise ValueError(
        f"Invalid CACHE value '{cache_option}'. Must be 'locmem' or 'valkey'."
    )

# The API is public and read-only: skipping session auth keeps responses free
# of Vary: Cookie so Cloudflare and browsers can share them.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
}

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "anthropic/claude-haiku-4-5")
WEREWOLF_LLM_MODEL = os.environ.get("WEREWOLF_LLM_MODEL", "anthropic/claude-haiku-5.5")
WEREWOLF_RUN_HOUR = int(os.environ.get("WEREWOLF_RUN_HOUR", "0"))
TICK_INTERVAL_MINUTES = int(os.environ.get("TICK_INTERVAL_MINUTES", "15"))
PLAN_HOUR = int(os.environ.get("PLAN_HOUR", "6"))
API_HIDE_FUTURE_TICKS = (
    os.environ.get("API_HIDE_FUTURE_TICKS", "false").lower() == "true"
)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {"level": LOG_LEVEL},
        "simulation": {"level": LOG_LEVEL},
        "world": {"level": LOG_LEVEL},
    },
}
