import os

from .base import *  # noqa: F403

DEBUG = False

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
]

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405

db_option = os.environ.get("DATABASE", "sqlite").lower()
if db_option == "postgres":
    required = {
        "SQL_DATABASE": None,
        "SQL_HOST": None,
        "SQL_USER": None,
        "SQL_PASSWORD": None,
    }
    for var in required:
        if not os.environ.get(var):
            raise ValueError(f"{var} environment variable not set.")
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["SQL_DATABASE"],
            "HOST": os.environ["SQL_HOST"],
            "PORT": os.environ.get("SQL_PORT", "5432"),
            "USER": os.environ["SQL_USER"],
            "PASSWORD": os.environ["SQL_PASSWORD"],
        }
    }
elif db_option != "sqlite":
    raise ValueError(
        f"Invalid DATABASE value '{db_option}'. Must be 'sqlite' or 'postgres'."
    )
