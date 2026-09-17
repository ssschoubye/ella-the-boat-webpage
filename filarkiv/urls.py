from django.urls import path

from . import views

urlpatterns = [
    path("", views.file_list, name="filarkiv"),
    path("upload/", views.upload_file, name="filarkiv_upload"),
    path("<int:pk>/hent/", views.download_file, name="filarkiv_download"),
    path("<int:pk>/slet/", views.delete_file, name="filarkiv_delete"),
]
