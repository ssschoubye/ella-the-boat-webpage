#!/bin/sh
# Container entrypoint. Starts as root only to make the bind-mounted data
# directory writable (the home server re-creates it as root:root on every
# deploy, and restored/copied-in files are usually root-owned), then drops to
# the unprivileged "app" user for everything else.
set -eu

DATA_DIR="${DJANGO_DATA_DIR:-/data}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR/media" "$DATA_DIR/backups"
    chown -R app:app "$DATA_DIR"
    # setpriv keeps HOME=/root, which app can't write to (gunicorn puts its
    # control socket there). /tmp is the only writable tmpfs.
    HOME=/tmp exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

python manage.py migrate --noinput

exec gunicorn config.wsgi \
    --bind 0.0.0.0:80 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --worker-tmp-dir /tmp \
    --access-logfile - \
    --error-logfile -
