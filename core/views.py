from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render


def home(request):
    """The one page that is public (ADR 0012).

    Anonymous visitors get the landing page; everyone signed in gets the real
    start page with the links into the site. Same URL either way, so nobody's
    bookmark changes and there is no redirect to notice.
    """
    if not request.user.is_authenticated:
        return render(request, "core/landing.html")
    return render(request, "core/home.html")


def placeholder(request, title, description):
    return render(request, "core/placeholder.html", {"title": title, "description": description})


def logbog(request):
    return placeholder(request, "Logbog", "Her kommer logbogen med ture, vejr og oplevelser på vandet.")


def skader(request):
    return placeholder(request, "Skader", "Her kommer en oversigt over skader og reparationer på Ella.")


def healthz(request):
    """Liveness probe for the container healthcheck; exempt from the login wall."""
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")
