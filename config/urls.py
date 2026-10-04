from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from adgang.forms import EmailLoginForm

urlpatterns = [
    path("admin/", admin.site.urls),
    # Sign-on. The login form takes an email address, because that is what
    # accounts are created with; adgang owns the invitation links that are the
    # only way an account comes into existence (ADR 0014).
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=EmailLoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("adgang.urls")),
    path("kalender/", include("booking.urls")),
    path("filarkiv/", include("filarkiv.urls")),
    path("vedligehold/", include("vedligehold.urls")),
    path("", include("core.urls")),
]
