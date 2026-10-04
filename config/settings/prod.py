"""
Production settings, used by the Docker image (see Dockerfile) on the home server.
Secrets/config come from environment variables — see .env.example and docs/deployment.md.

Request path: Cloudflare (TLS) -> cloudflared -> Caddy -> gunicorn in this container.
"""
from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, env

DEBUG = False

# No default, unlike base.py. If /etc/home-server/ella.env is missing or does
# not contain the key, the container must fail to start -- the alternative is
# serving production with base.py's "django-insecure-change-me-in-.env", which
# would sign session cookies with a value that is public in this repo.
SECRET_KEY = env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["ella.molder.app", "localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=["https://ella.molder.app"])

# All state lives under one directory, bind-mounted from /srv/state/ella on the
# server: the SQLite database, uploaded files and the backup snapshot that
# `manage.py snapshot_db` writes before each restic run.
DATA_DIR = env.path("DJANGO_DATA_DIR", default="/data")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR("db.sqlite3"),
        "OPTIONS": {
            # IMMEDIATE + a busy timeout avoids "database is locked" when two
            # gunicorn workers write at once; WAL lets reads continue meanwhile.
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}

MEDIA_ROOT = DATA_DIR("media")

# No Nginx in front: WhiteNoise serves the static files collected into the
# image at build time. It must sit directly after SecurityMiddleware.
MIDDLEWARE = MIDDLEWARE.copy()
MIDDLEWARE.insert(MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
                  "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Cloudflare terminates TLS and forces HTTPS at the edge; cloudflared sends
# X-Forwarded-Proto: https and Caddy passes it through. Redirecting here as well
# would break the container's plain-HTTP healthcheck, so it is off by default.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# allauth builds the Google callback URL with request.build_absolute_uri, so
# the header above is what actually makes it https. This is belt and braces
# for the paths that consult the setting instead, and it has to be https or
# Google rejects the redirect_uri as not matching the registered one.
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Both handled by Cloudflare at the edge (HSTS and "Always Use HTTPS"), so
# `check --deploy` should not nag about them here.
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]
