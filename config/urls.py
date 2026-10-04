from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Sign-on. allauth owns /accounts/login/, the Google callback and logout;
    # adgang owns the invitation links that allow a signup at all.
    path("accounts/", include("allauth.urls")),
    path("", include("adgang.urls")),
    path("kalender/", include("booking.urls")),
    path("filarkiv/", include("filarkiv.urls")),
    path("vedligehold/", include("vedligehold.urls")),
    path("", include("core.urls")),
]
