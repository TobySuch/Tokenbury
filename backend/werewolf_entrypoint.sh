#!/bin/bash
set -e
export DJANGO_SETTINGS_MODULE=config.settings.production

uv run python manage.py migrate --noinput

POLL_INTERVAL_MINUTES=${WEREWOLF_POLL_INTERVAL_MINUTES:-15}
POLL_INTERVAL_SECONDS=$(( POLL_INTERVAL_MINUTES * 60 ))
echo "Werewolf: polling every ${POLL_INTERVAL_MINUTES} minutes (a day runs once per day after WEREWOLF_RUN_HOUR)"

while true; do
  uv run python manage.py run_day --if-due
  sleep "$POLL_INTERVAL_SECONDS"
done
