from django.contrib.auth.views import redirect_to_login

# Prefixes that anyone may reach. `/accounts/` is allauth: the login page
# itself and the Google callback. `/invitation/` is how a new person gets in
# before they have an account at all.
EXEMPT_PREFIXES = ("/admin/", "/static/", "/healthz/", "/accounts/", "/invitation/")

# Exact paths that anyone may reach. The front page is public (ADR 0012); it
# shows the boat and a way in, and `core.views.home` serves the real start
# page instead once you are signed in. Matched exactly, because "/" as a
# prefix would of course exempt the entire site.
EXEMPT_PATHS = ("/",)


class LoginRequiredMiddleware:
    """Require an authenticated session for every page except the public front
    page, the sign-on flow, /admin/ (which has its own login), static files
    and the health check."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            not request.user.is_authenticated
            and request.path not in EXEMPT_PATHS
            and not request.path.startswith(EXEMPT_PREFIXES)
        ):
            # login_url=None means settings.LOGIN_URL, resolved for us.
            return redirect_to_login(request.get_full_path())
        return self.get_response(request)
