from django.urls import path

from . import views

urlpatterns = [
    path("", views.board, name="vedligehold"),
    path("ny/", views.ticket_create, name="vedligehold_ticket_create"),
    path("arkiv/", views.archive_list, name="vedligehold_archive"),
    path("<int:pk>/", views.ticket_detail, name="vedligehold_ticket_detail"),
    path("<int:pk>/flyt/", views.move_ticket, name="vedligehold_ticket_move"),
    path("<int:pk>/arkiver/", views.archive_ticket, name="vedligehold_ticket_archive"),
    path("<int:pk>/genaabn/", views.reopen_ticket, name="vedligehold_ticket_reopen"),
]
