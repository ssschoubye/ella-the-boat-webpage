import uuid

from django.conf import settings
from django.db import models

REPEAT_CHOICES = [
    ("none", "Gentager ikke"),
    ("weekly", "Hver uge"),
    ("biweekly", "Hver 2. uge"),
    ("monthly", "Hver måned"),
]

# There used to be a hardcoded BOOKER_CHOICES list of the group's names here,
# imported by filarkiv and vedligehold as well. Adding a person meant editing
# it, generating migrations in three apps and deploying. Now that everyone has
# a real account (ADR 0010), these fields point at it instead and the list
# maintains itself -- see ADR 0011.


class Booking(models.Model):
    title = models.CharField("Titel", max_length=200)
    # SET_NULL, not CASCADE: deleting an account must never take the boat's
    # booking history with it. Templates render a missing one as "Ukendt".
    booker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Booker",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    start_date = models.DateTimeField("Startdato")
    end_date = models.DateTimeField("Slutdato", help_text="Same as start date for a single-day trip.")
    notes = models.TextField("Noter", blank=True)
    series_id = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.title} ({self.start_date})"
