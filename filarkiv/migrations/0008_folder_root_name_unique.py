from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("filarkiv", "0007_folder_required"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="folder",
            constraint=models.UniqueConstraint(
                condition=models.Q(("parent", None)),
                fields=("name",),
                name="filarkiv_folder_unique_root_name",
            ),
        ),
    ]
