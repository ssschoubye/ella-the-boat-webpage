from django.contrib import admin

from .models import ArchiveFile


@admin.register(ArchiveFile)
class ArchiveFileAdmin(admin.ModelAdmin):
    list_display = ("title", "uploaded_by", "uploaded_at")
    list_filter = ("uploaded_by",)
    search_fields = ("title", "description")
