"""Name the django.contrib.sites row after the real host.

allauth requires contrib.sites, whose initial migration seeds "example.com".
Nothing load-bearing reads it -- the OAuth redirect URI is built from the
request and we send no mail -- but a row saying example.com in the admin is
the kind of thing that sends someone debugging in the wrong direction.
"""
from django.conf import settings
from django.db import migrations

DOMAIN = settings.PUBLIC_BASE_URL.split("://")[-1]


def set_domain(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": DOMAIN, "name": "Ella"},
    )


def reset_domain(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.filter(pk=settings.SITE_ID).update(domain="example.com", name="example.com")


class Migration(migrations.Migration):

    dependencies = [
        ("adgang", "0001_initial"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [migrations.RunPython(set_domain, reset_domain)]
