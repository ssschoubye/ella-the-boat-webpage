from django.urls import path

from . import views

urlpatterns = [
    path("invitation/<str:token>/", views.invitation, name="invitation"),
]
