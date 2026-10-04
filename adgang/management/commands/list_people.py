"""List the accounts on the site, and flag anything odd about them.

    docker exec -u app ella python manage.py list_people

Exists so that checking who has access is not a shell one-liner pasted out of
a document, which is how typos get run against production.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email
from django.utils import timezone

User = get_user_model()


def looks_like_email(value):
    try:
        validate_email(value)
    except ValidationError:
        return False
    return True


class Command(BaseCommand):
    help = "List the site's accounts, with a warning for any that cannot use /login/."

    def handle(self, *args, **options):
        users = User.objects.order_by("username")
        if not users.exists():
            self.stdout.write("No accounts yet. Mint an invitation with `manage.py invite`.")
            return

        self.stdout.write(f"{'login (username)':38} {'name':14} {'role':10} last seen")
        self.stdout.write("-" * 86)

        warnings = []
        for user in users:
            role = "superuser" if user.is_superuser else ("staff" if user.is_staff else "member")
            if not user.is_active:
                role += " INACTIVE"
            last = (
                timezone.localtime(user.last_login).strftime("%Y-%m-%d %H:%M")
                if user.last_login
                else "never"
            )
            self.stdout.write(
                f"{user.username:38} {(user.first_name or '-'):14} {role:10} {last}"
            )

            # The username is the login identifier and /login/ is an email
            # field, so a non-email username can only get in via /admin/.
            if not looks_like_email(user.username):
                warnings.append(
                    f"{user.username!r} is not an email address, so it cannot sign in at "
                    f"/login/ -- only at /admin/. Fix with: "
                    f"manage.py rename_login {user.username} <their-email>"
                )
            if user.email and user.email.lower() != user.username.lower():
                warnings.append(
                    f"{user.username!r} has a different email on file ({user.email!r}). "
                    f"Harmless, but the username is what they log in with."
                )

        for warning in warnings:
            self.stdout.write(self.style.WARNING("\n! " + warning))
