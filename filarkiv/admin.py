from django.contrib import admin

from .models import ArchiveFile, Folder


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("__str__", "parent", "created_at")
    search_fields = ("name",)


@admin.register(ArchiveFile)
class ArchiveFileAdmin(admin.ModelAdmin):
    list_display = ("title", "folder", "uploaded_by", "uploaded_at")
    list_filter = ("uploaded_by", "folder")
    search_fields = ("title", "description")
