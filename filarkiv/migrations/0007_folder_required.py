import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("filarkiv", "0006_root_folders"),
    ]

    operations = [
        migrations.AlterField(
            model_name="archivefile",
            name="folder",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="files",
                to="filarkiv.folder",
                verbose_name="Mappe",
            ),
        ),
    ]
