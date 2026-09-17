import uuid

from django.db import models

REPEAT_CHOICES = [
    ("none", "Gentager ikke"),
    ("weekly", "Hver uge"),
    ("biweekly", "Hver 2. uge"),
    ("monthly", "Hver måned"),
]

BOOKER_CHOICES = [
    ("person_1", "Emil"),
    ("person_2", "Anton"),
    ("person_3", "Kathrine"),
    ("person_4", "Frederikke"),
    ("person_5", "Søren"),
    ("person_6", "Person 6"),
]


class Booking(models.Model):
    title = models.CharField("Titel", max_length=200)
    booker = models.CharField("Booker", max_length=20, choices=BOOKER_CHOICES, default=BOOKER_CHOICES[0][0])
    start_date = models.DateTimeField("Startdato")
    end_date = models.DateTimeField("Slutdato", help_text="Same as start date for a single-day trip.")
    notes = models.TextField("Noter", blank=True)
    series_id = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.title} ({self.start_date})"
