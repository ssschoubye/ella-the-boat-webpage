"""Mint an invitation link from the command line.

    docker exec -it -u app ella python manage.py invite "Anton"

The admin at /invitation/ does the same thing with a form; this exists so a
link can be made without a working login, which matters the first time.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from adgang.models import Invitation


class Command(BaseCommand):
    help = "Create an invitation link and print it."

    def add_arguments(self, parser):
        parser.add_argument("label", help="Who it is for; only for your own overview.")
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Days until the link expires. Defaults to DJANGO_INVITATION_VALID_DAYS.",
        )

    def handle(self, *args, **options):
        invitation = Invitation(label=options["label"])
        if options["days"] is not None:
            invitation.expires_at = timezone.now() + timedelta(days=options["days"])
        invitation.save()

        self.stdout.write(self.style.SUCCESS(invitation.url))
        self.stdout.write(
            f"Gyldigt til {timezone.localtime(invitation.expires_at):%d-%m-%Y %H:%M}. Kan bruges én gang."
        )
