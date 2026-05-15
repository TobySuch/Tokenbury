#!/bin/bash
set -e
export DJANGO_SETTINGS_MODULE=config.settings.production

uv run python manage.py migrate --noinput

POLL_INTERVAL_MINUTES=${TICKER_POLL_INTERVAL_MINUTES:-5}
POLL_INTERVAL_SECONDS=$(( POLL_INTERVAL_MINUTES * 60 ))
echo "Auto-ticker: polling every ${POLL_INTERVAL_MINUTES} minutes (tick interval controlled by TICK_INTERVAL_MINUTES)"

while true; do
  uv run python manage.py run_ticker --catchup
  sleep "$POLL_INTERVAL_SECONDS"
done
