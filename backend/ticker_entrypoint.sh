#!/bin/bash
set -e
export DJANGO_SETTINGS_MODULE=config.settings.production

uv run python manage.py migrate --noinput

INTERVAL_MINUTES=${TICK_INTERVAL_MINUTES:-15}
INTERVAL_SECONDS=$(( INTERVAL_MINUTES * 60 ))
echo "Auto-ticker: running every ${INTERVAL_MINUTES} minutes"

while true; do
  uv run python manage.py run_ticker --catchup
  sleep "$INTERVAL_SECONDS"
done
