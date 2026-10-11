from django.urls import path

from . import views

urlpatterns = [
    path("", views.file_list, name="filarkiv"),
    path("upload/", views.upload_file, name="filarkiv_upload"),
    path("mappe/<int:pk>/", views.folder_detail, name="filarkiv_folder"),
    path("mappe/<int:pk>/ny/", views.folder_create, name="filarkiv_folder_create"),
    path("mappe/<int:pk>/omdob/", views.folder_rename, name="filarkiv_folder_rename"),
    path("mappe/<int:pk>/slet/", views.folder_delete, name="filarkiv_folder_delete"),
    path("<int:pk>/rediger/", views.file_edit, name="filarkiv_edit"),
    path("<int:pk>/vis/", views.view_image, name="filarkiv_view"),
    path("<int:pk>/miniature/", views.thumbnail, name="filarkiv_thumbnail"),
    path("<int:pk>/hent/", views.download_file, name="filarkiv_download"),
    path("<int:pk>/slet/", views.delete_file, name="filarkiv_delete"),
]
