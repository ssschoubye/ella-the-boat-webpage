"""Create the two fixed top-level folders and sort existing files into them:
images into Billeder, everything else into Filer."""
from django.db import migrations

from filarkiv.models import is_image_name


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
