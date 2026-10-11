"""Create the two fixed top-level folders and sort existing files into them:
images into Billeder, everything else into Filer."""
from pathlib import Path

from django.db import migrations

# Frozen on purpose, rather than imported from filarkiv.models: this
# migration has to sort files the same way forever, so that a database built
# fresh in CI or on a new machine ends up where production did.
IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "gif", "webp"}


def is_image_name(name):
    return Path(name).suffix.lstrip(".").lower() in IMAGE_SUFFIXES


def create_roots(apps, schema_editor):
    Folder = apps.get_model("filarkiv", "Folder")
    ArchiveFile = apps.get_model("filarkiv", "ArchiveFile")

    billeder = Folder.objects.create(name="Billeder", root_key="billeder")
    filer = Folder.objects.create(name="Filer", root_key="filer")

    for archive_file in ArchiveFile.objects.all():
        archive_file.folder = billeder if is_image_name(archive_file.file.name) else filer
        archive_file.save(update_fields=["folder"])


def remove_roots(apps, schema_editor):
    Folder = apps.get_model("filarkiv", "Folder")
    ArchiveFile = apps.get_model("filarkiv", "ArchiveFile")

    # Going back to a flat archive: every file moves to the top level, and
    # every folder, including ones people made, goes.
    ArchiveFile.objects.update(folder=None)
    while Folder.objects.exists():
        Folder.objects.filter(children__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("filarkiv", "0005_folder_and_thumbnail"),
    ]

    operations = [
        migrations.RunPython(create_roots, remove_roots),
    ]
