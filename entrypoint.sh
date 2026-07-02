#!/bin/sh
# Runs on every container start (dev and prod alike).
# Applies any pending migrations (idempotent — safe to run every time),
# then hands off to the container's CMD: runserver in dev, collectstatic
# + gunicorn in prod.
set -e
python manage.py migrate --noinput
exec "$@"
