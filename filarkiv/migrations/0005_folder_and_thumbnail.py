import django.db.models.deletion
from django.db import migrations, models

import filarkiv.models


class Migration(migrations.Migration):

    dependencies = [
        ("filarkiv", "0004_uploaded_by_as_account"),
    ]

    operations = [
        migrations.CreateModel(
            name="Folder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="Navn")),
                ("root_key", models.CharField(blank=True, editable=False, max_length=20, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Oprettet")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="filarkiv.folder",
                        verbose_name="Overmappe",
                    ),
                ),
            ],
            options={
                "verbose_name": "mappe",
                "verbose_name_plural": "mapper",
                "ordering": ["name"],
                "constraints": [
                    models.UniqueConstraint(fields=("parent", "name"), name="filarkiv_folder_unique_name_per_parent")
                ],
            },
        ),
        migrations.AddField(
            model_name="archivefile",
            name="thumbnail",
            field=models.FileField(
                blank=True,
                editable=False,
                upload_to=filarkiv.models.thumbnail_upload_path,
                verbose_name="Miniature",
            ),
        ),
        # Nullable for now; 0006 fills it in and 0007 makes it required.
        migrations.AddField(
            model_name="archivefile",
            name="folder",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="files",
                to="filarkiv.folder",
                verbose_name="Mappe",
            ),
        ),
    ]
