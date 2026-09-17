from django.contrib.auth.views import redirect_to_login
from django.urls import reverse

EXEMPT_PREFIXES = ("/admin/", "/static/")


class LoginRequiredMiddleware:
    """Require an authenticated session for every page except /admin/, static
    files, and the login page itself."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        login_path = reverse("login")
        if (
            not request.user.is_authenticated
            and request.path != login_path
            and not request.path.startswith(EXEMPT_PREFIXES)
        ):
            return redirect_to_login(request.get_full_path(), login_url=login_path)
        return self.get_response(request)
