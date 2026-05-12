#!/bin/sh
set -e
export DJANGO_SETTINGS_MODULE=config.settings.production
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput
exec uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000
