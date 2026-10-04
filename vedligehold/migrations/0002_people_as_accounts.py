"""Point Ticket.created_by and Comment.author at real accounts.

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
    Ticket = apps.get_model("vedligehold", "Ticket")
    Comment = apps.get_model("vedligehold", "Comment")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for key, name in LEGACY_NAMES.items():
        user = User.objects.filter(first_name__iexact=name).first()
        if user is None:
            continue
        Ticket.objects.filter(legacy_created_by=key).update(created_by=user.pk)
        Comment.objects.filter(legacy_author=key).update(author=user.pk)


def unmatch(apps, schema_editor):
    Ticket = apps.get_model("vedligehold", "Ticket")
    Comment = apps.get_model("vedligehold", "Comment")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for key, name in LEGACY_NAMES.items():
        user = User.objects.filter(first_name__iexact=name).first()
        if user is None:
            continue
        Ticket.objects.filter(created_by=user.pk).update(legacy_created_by=key)
        Comment.objects.filter(author=user.pk).update(legacy_author=key)


class Migration(migrations.Migration):

    dependencies = [
        ("vedligehold", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="ticket", old_name="created_by", new_name="legacy_created_by"
        ),
        migrations.RenameField(
            model_name="comment", old_name="author", new_name="legacy_author"
        ),
        migrations.AddField(
            model_name="ticket",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tickets",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Oprettet af",
            ),
        ),
        migrations.AddField(
            model_name="comment",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ticket_comments",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Fra",
            ),
        ),
        migrations.RunPython(match_accounts, unmatch),
        migrations.RemoveField(model_name="ticket", name="legacy_created_by"),
        migrations.RemoveField(model_name="comment", name="legacy_author"),
    ]
