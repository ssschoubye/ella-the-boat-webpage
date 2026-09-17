from django.urls import path

from . import views

urlpatterns = [
    path("", views.month_view, name="kalender"),
    path("uge/", views.week_view, name="kalender_uge"),
    path("uge/<int:year>/<int:week>/", views.week_view, name="kalender_uge_at"),
    path("liste/", views.list_view, name="kalender_liste"),
    path("tilfoj/", views.add_booking, name="tilfoj_tur"),
    path("<int:pk>/rediger/", views.edit_booking, name="rediger_tur"),
    path("<int:pk>/slet/", views.delete_booking, name="slet_tur"),
    path("<int:pk>/slet-serie/", views.delete_series, name="slet_serie"),
    path("<int:year>/<int:month>/", views.month_view, name="kalender_month"),
]
