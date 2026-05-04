from .base import *  # noqa: F403

DEBUG = True

SECRET_KEY = "local-dev-secret-key-change-in-production"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
]
