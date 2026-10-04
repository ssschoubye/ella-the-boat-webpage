import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def archive_upload_path(instance, filename):
    return f"filarkiv/{uuid.uuid4().hex}/{filename}"


class ArchiveFile(models.Model):
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beskrivelse", blank=True)
    file = models.FileField("Fil", upload_to=archive_upload_path)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Uploadet af",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploads",
    )
    uploaded_at = models.DateTimeField("Uploadet", auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return Path(self.file.name).name

    @property
    def extension(self):
        return Path(self.file.name).suffix.lstrip(".").upper()
