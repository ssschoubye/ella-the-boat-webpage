"""Change the email address an account logs in with.

    docker exec -u app ella python manage.py rename_login soren soren@example.com

The username *is* the login identifier (ADR 0014), so this is what to use when
`createsuperuser` was answered with a short name instead of an email address,
or when someone changes address. Nothing in the database references the
username -- bookings, uploads and tickets point at the user's id -- so a
rename keeps all of their history.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

User = get_user_model()


class Command(BaseCommand):
    help = "Change the email address (username) an account logs in with."

    def add_arguments(self, parser):
        parser.add_argument("current", help="The account's current username.")
        parser.add_argument("new_email", help="The email address it should log in with.")

    def handle(self, *args, **options):
        user = User.objects.filter(username=options["current"]).first()
        if user is None:
            raise CommandError(
                f"No account with username {options['current']!r}. "
                f"Run `manage.py list_people` to see them."
            )

        # Lower-cased to match SignupForm and EmailLoginForm, which both
        # normalise, so that Anton@ and anton@ cannot become two accounts.
        new_email = options["new_email"].strip().lower()

        try:
            validate_email(new_email)
        except ValidationError:
            raise CommandError(f"{new_email!r} is not a valid email address.")

        max_length = User._meta.get_field("username").max_length
        if len(new_email) > max_length:
            raise CommandError(f"{new_email!r} is longer than {max_length} characters.")

        clash = User.objects.filter(username=new_email).exclude(pk=user.pk).first()
        if clash is not None:
            raise CommandError(
                f"Another account already logs in with {new_email!r}. "
                f"Deactivate one of them in /admin/ rather than merging them here."
            )

        was = user.username
        user.username = new_email
        user.email = new_email
        user.save(update_fields=["username", "email"])

        self.stdout.write(
            self.style.SUCCESS(f"{was!r} now logs in with {new_email!r}.")
        )
        self.stdout.write("Their existing bookings, uploads and tickets are unaffected.")
