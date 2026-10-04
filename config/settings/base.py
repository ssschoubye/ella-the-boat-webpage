"""
Settings shared by every environment (local dev and production).
Environment-specific overrides live in dev.py and prod.py.
"""
from datetime import timedelta
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / "subdir".
# base.py lives in config/settings/, so go up three levels to reach the project root.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Read a .env file from the project root if one exists (local dev convenience).
# In production you'd typically set real environment variables instead.
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-change-me-in-.env")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Lockout on the login form. This is the main defence now that the login
    # page is publicly reachable (ADR 0014).
    "axes",
    # Local apps
    "core",
    "adgang",
    "booking",
    "filarkiv",
    "vedligehold",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.LoginRequiredMiddleware",
    # Must be last: it turns the PermissionDenied that AxesStandaloneBackend
    # raises into the lockout page instead of a bare 403.
    "axes.middleware.AxesMiddleware",
]

# ---------------------------------------------------------------- sign-on
# The whole of it: an invitation link lets one person create one account with
# any email address and a password of their choosing, and that is the only way
# an account comes into existence (ADR 0014). There is no list of allowed
# addresses, no identity provider and no outbound email.
#
# The email is the username. It is never verified -- the invitation link is
# the proof of authorisation, and the address is only a label and a way to
# reach someone.

AUTHENTICATION_BACKENDS = [
    # Must come first. It raises PermissionDenied for a locked-out client
    # before ModelBackend gets to check the password.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# Where invitation links are built from, because a link is minted by a
# management command or the admin and has no request to derive a host from.
PUBLIC_BASE_URL = env("DJANGO_PUBLIC_BASE_URL", default="https://ella.molder.app").rstrip("/")

# How long a freshly minted invitation stays usable.
INVITATION_VALID_DAYS = env.int("DJANGO_INVITATION_VALID_DAYS", default=30)

# --- django-axes ---
# This is the defence that matters. The login page is publicly reachable and
# passwords are chosen by people who are not thinking about passwords, so the
# limit is what stands between the site and someone trying a list.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
# Lock the (username, ip) pair as well as the IP on its own: the pair stops a
# slow grind against one account from several addresses, while the bare IP
# stops one address working through every account.
AXES_LOCKOUT_PARAMETERS = ["ip_address", ["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/lockout.html"
# Nothing can reach this app except through the Cloudflare Tunnel, so
# CF-Connecting-IP is set by cloudflared and cannot be spoofed by a client.
# Without this, every attempt would be attributed to Caddy's container IP and
# one attacker would lock out the whole group.
AXES_IPWARE_META_PRECEDENCE_ORDER = [
    "HTTP_CF_CONNECTING_IP",
    "HTTP_X_FORWARDED_FOR",
    "REMOTE_ADDR",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Set to your own timezone, e.g. "Europe/Copenhagen"
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", default="Europe/Copenhagen")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic target in production

# Uploaded files (Filarkiv). Not served directly by Nginx/MEDIA_URL — they're
# only reachable through filarkiv's own login-protected download view, so the
# whole archive stays behind the site's login wall.
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Everything goes to stdout/stderr; in production Docker collects it.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
