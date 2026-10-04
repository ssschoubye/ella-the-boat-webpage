"""Point ArchiveFile.uploaded_by at a real account.

Same shape and the same reasoning as booking/0005_booker_as_account.py.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

LEGACY_NAMES = {
    "person_1": "Emil",
    "person_2": "Anton",
    "person_3": "Kathrine",
    "person_4": "Frederikke",
    "person_5": "Søren",
    "person_6": "Person 6",
}


def match_accounts(apps, schema_editor):
    ArchiveFile = apps.get_model("filarkiv", "ArchiveFile")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for key, name in LEGACY_NAMES.items():
        user = User.objects.filter(first_name__iexact=name).first()
        if user is not None:
            ArchiveFile.objects.filter(legacy_uploaded_by=key).update(uploaded_by=user.pk)


def unmatch(apps, schema_editor):
    ArchiveFile = apps.get_model("filarkiv", "ArchiveFile")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for key, name in LEGACY_NAMES.items():
        user = User.objects.filter(first_name__iexact=name).first()
        if user is not None:
            ArchiveFile.objects.filter(uploaded_by=user.pk).update(legacy_uploaded_by=key)


class Migration(migrations.Migration):

    dependencies = [
        ("filarkiv", "0003_remove_archivefile_folder_delete_folder"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="archivefile",
            old_name="uploaded_by",
            new_name="legacy_uploaded_by",
        ),
        migrations.AddField(
            model_name="archivefile",
            name="uploaded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="uploads",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Uploadet af",
            ),
        ),
        migrations.RunPython(match_accounts, unmatch),
        migrations.RemoveField(model_name="archivefile", name="legacy_uploaded_by"),
    ]
