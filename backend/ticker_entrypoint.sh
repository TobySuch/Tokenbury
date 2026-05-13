#!/bin/bash
set -e
export DJANGO_SETTINGS_MODULE=config.settings.production

python manage.py migrate --noinput

INTERVAL_MINUTES=${TICK_INTERVAL_MINUTES:-15}
INTERVAL_SECONDS=$(( INTERVAL_MINUTES * 60 ))
echo "Auto-ticker: running every ${INTERVAL_MINUTES} minutes"

while true; do
  python manage.py run_ticker --catchup
  sleep "$INTERVAL_SECONDS"
done
