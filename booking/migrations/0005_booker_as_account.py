"""Point Booking.booker at a real account instead of a hardcoded name.

Written by hand rather than generated, because a generated AlterField from
CharField to ForeignKey asks SQLite to cast "person_1" to an integer. On a
fresh database that happens to work -- there are no rows -- but it would
quietly ruin an existing one. So the old column is renamed aside, the new one
filled in from it where a matching account exists, and only then dropped.

Accounts are created by signing in with Google (ADR 0010), so on a database
that predates that there are no users to match and every booker ends up NULL,
which templates render as "Ukendt".
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

# The list that used to live in booking/models.py as BOOKER_CHOICES.
LEGACY_NAMES = {
    "person_1": "Emil",
    "person_2": "Anton",
    "person_3": "Kathrine",
    "person_4": "Frederikke",
    "person_5": "Søren",
    "person_6": "Person 6",
}


def match_accounts(apps, schema_editor):
    Booking = apps.get_model("booking", "Booking")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    by_name = {}
    for key, name in LEGACY_NAMES.items():
        user = User.objects.filter(first_name__iexact=name).first()
        if user is not None:
            by_name[key] = user.pk

    for key, user_pk in by_name.items():
        Booking.objects.filter(legacy_booker=key).update(booker=user_pk)


def unmatch(apps, schema_editor):
    """Reverse: put back a legacy key where the account's name still matches."""
    Booking = apps.get_model("booking", "Booking")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for key, name in LEGACY_NAMES.items():
        user = User.objects.filter(first_name__iexact=name).first()
        if user is not None:
            Booking.objects.filter(booker=user.pk).update(legacy_booker=key)


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0004_booking_series_id_alter_booking_booker"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="booking",
            old_name="booker",
            new_name="legacy_booker",
        ),
        migrations.AddField(
            model_name="booking",
            name="booker",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bookings",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Booker",
            ),
        ),
        migrations.RunPython(match_accounts, unmatch),
        migrations.RemoveField(model_name="booking", name="legacy_booker"),
    ]
