"""
Production settings, meant for the Hetzner server.
Point DJANGO_SETTINGS_MODULE=config.settings.prod when deploying.
All secrets/config here come from environment variables — see .env.example.
"""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# Example: yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

DATABASES = {
    "default": env.db("DATABASE_URL"),  # e.g. postgres://user:pass@localhost:5432/dbname
}

# Basic hardening for serving over HTTPS behind Nginx.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
