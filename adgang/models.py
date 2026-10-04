"""Invitations.

Access to the site is not a list of allowed email addresses kept somewhere and
edited whenever the group changes. It is a one-off link: you send someone an
invitation, they pick an email and a password on the page it opens, and their
account exists from then on (ADR 0014).

So the only thing stored here is the link itself, plus enough to tell whether
it has already been used.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

# How many bytes of randomness go into a token. 32 bytes is 256 bits, which is
# the security of the whole scheme: anyone holding a token can create an
# account, so it has to be unguessable rather than merely unique.
TOKEN_BYTES = 32

def generate_token():
    return secrets.token_urlsafe(TOKEN_BYTES)


def default_expiry():
    return timezone.now() + timedelta(days=settings.INVITATION_VALID_DAYS)


class Invitation(models.Model):
    """A single-use link that lets one person create an account."""

    token = models.CharField(max_length=64, unique=True, default=generate_token, editable=False)
    label = models.CharField(
        "Til",
        max_length=100,
        help_text="Hvem invitationen er til. Kun til dit eget overblik.",
    )
    created_at = models.DateTimeField("Oprettet", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
        editable=False,
    )
    expires_at = models.DateTimeField("Udløber", default=default_expiry)
    revoked = models.BooleanField(
        "Tilbagekaldt",
        default=False,
        help_text="Sæt flueben for at gøre linket ubrugeligt uden at slette det.",
    )
    accepted_at = models.DateTimeField("Brugt", null=True, blank=True, editable=False)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitation",
        editable=False,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "invitation"
        verbose_name_plural = "invitationer"

    def __str__(self):
        return f"Invitation til {self.label}"

    @property
    def is_usable(self):
        return not self.revoked and self.accepted_at is None and self.expires_at > timezone.now()

    @property
    def status(self):
        """Why the link does or doesn't work, in Danish, for the admin list."""
        if self.accepted_at is not None:
            return "Brugt"
        if self.revoked:
            return "Tilbagekaldt"
        if self.expires_at <= timezone.now():
            return "Udløbet"
        return "Klar"

    def get_absolute_url(self):
        return reverse("invitation", args=[self.token])

    @property
    def url(self):
        """The full link to send. Built from a setting, because an invitation
        is usually minted by a management command with no request in sight."""
        return f"{settings.PUBLIC_BASE_URL}{self.get_absolute_url()}"

    def accept(self, user):
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save(update_fields=["accepted_at", "accepted_by"])
