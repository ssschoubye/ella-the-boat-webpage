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
# Two ways in, and signing up requires an unused invitation link either way:
# Google (ADR 0010), or a one-time code emailed to any address at all
# (ADR 0013). There is no password login and no list of allowed emails to
# maintain. See docs/security.md.
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
# Nobody gets a password. SOCIALACCOUNT_ONLY is deliberately NOT set: it would
# disable the whole local-account machinery, and the email code path needs it.
# What keeps passwords out is ACCOUNT_SIGNUP_FIELDS below, which omits them, so
# accounts are created with an unusable password and there is nothing to reset.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]

# Email codes, not links: a code can be read off a phone and typed into the
# laptop the browser is already open on, and it cannot be prefetched by a
# mail client the way a one-click link can.
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_TIMEOUT = 10 * 60
ACCOUNT_LOGIN_BY_CODE_MAX_ATTEMPTS = 3

# A local signup has to prove it owns the address, by the same kind of code.
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
# Google has already verified the address it hands us, so a social signup is
# not asked to do it again.
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"

# Do not confirm or deny that an address has an account. Asking for a code for
# an unknown address sends a "no such account" mail instead of saying so on
# screen, which is also why the request form never reports failure.
ACCOUNT_PREVENT_ENUMERATION = True

# allauth's own per-view limits are left at their defaults, which are already
# strict where it matters: 3 code requests per minute per address, 20 per
# minute per IP, and 3 wrong codes before the attempt is dead. Those last
# three live in the session rather than the cache, so a wrong-code brute force
# is bounded even though the default LocMemCache is per-gunicorn-worker.
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Ella] "
# Go straight from Google back into the site: no intermediate signup form to
# fill in. This is the whole point of the design.
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_LOGOUT_ON_GET = False

# These two adapters are what make the site invite-only. BOTH matter now:
# the account adapter gates the email path, the social one gates Google.
ACCOUNT_ADAPTER = "adgang.adapters.InvitationOnlyAccountAdapter"
SOCIALACCOUNT_ADAPTER = "adgang.adapters.InvitationOnlySocialAccountAdapter"

# --- sending mail ---
# Only ever used for sign-in and verification codes; the site sends no other
# mail. The console backend is the default so local development needs no SMTP
# at all -- the code is printed in the runserver output. prod.py switches to
# real SMTP.
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=True)
EMAIL_TIMEOUT = env.int("DJANGO_EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="Ella <noreply@molder.app>")

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
