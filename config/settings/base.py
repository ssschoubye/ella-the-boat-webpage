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
    # django.contrib.sites is required by allauth.
    "django.contrib.sites",
    # Sign-on: Google only, invite-gated (ADR 0010).
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Lockout for the one remaining password form, /admin/ (ADR 0010).
    "axes",
    # Local apps
    "core",
    "adgang",
    "booking",
    "filarkiv",
    "vedligehold",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # allauth needs this after AuthenticationMiddleware; it rejects requests
    # whose session was authenticated by something it doesn't know about.
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.LoginRequiredMiddleware",
    # Must be last: it turns the PermissionDenied that AxesStandaloneBackend
    # raises into the lockout page instead of a bare 403.
    "axes.middleware.AxesMiddleware",
]

# ---------------------------------------------------------------- sign-on
# Google sign-in through allauth, and signing up requires an unused invitation
# link. There is no self-service password login and no list of allowed emails
# to maintain: see ADR 0010 and docs/security.md.
#
# The one password form left in the site is /admin/, which django-axes locks
# out after repeated failures. It is the break-glass path for the superuser.

AUTHENTICATION_BACKENDS = [
    # Must come first. It raises PermissionDenied for a locked-out client
    # before any other backend gets to check the credentials.
    "axes.backends.AxesStandaloneBackend",
    # Keeps /admin/ working for the superuser, which is the way back in if
    # Google or allauth ever breaks.
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# Where invitation links are built from, because a link is minted by a
# management command or the admin and has no request to derive a host from.
PUBLIC_BASE_URL = env("DJANGO_PUBLIC_BASE_URL", default="https://ella.molder.app").rstrip("/")

# How long a freshly minted invitation stays usable.
INVITATION_VALID_DAYS = env.int("DJANGO_INVITATION_VALID_DAYS", default=30)

# --- allauth ---
# Nobody gets a password, so there is nothing to reset and no SMTP to set up.
SOCIALACCOUNT_ONLY = True
ACCOUNT_EMAIL_VERIFICATION = "none"
# Google has already verified the address, and we cannot send mail anyway.
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
# Go straight from Google back into the site: no intermediate signup form to
# fill in. This is the whole point of the design.
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_LOGOUT_ON_GET = False

# These two adapters are what make the site invite-only.
ACCOUNT_ADAPTER = "adgang.adapters.NoLocalSignupAccountAdapter"
SOCIALACCOUNT_ADAPTER = "adgang.adapters.InvitationOnlySocialAccountAdapter"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        # Configured from the environment rather than the SocialApp table, so
        # the credentials come from sops and are not part of the backup.
        "APP": {
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": env("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        # "online" because we never call a Google API on the user's behalf
        # after login, so there is no refresh token worth storing.
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# --- django-axes ---
# Only /admin/ accepts a password, so the limit can be strict.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "account/lockout.html"
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
