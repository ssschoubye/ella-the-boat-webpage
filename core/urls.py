from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("logbog/", views.logbog, name="logbog"),
    path("skader/", views.skader, name="skader"),
]
