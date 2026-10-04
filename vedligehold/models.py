from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

SWEEP_AFTER = timedelta(days=30)

STATUS_ONSKE = "onske"
STATUS_REPARATION = "reparation"
STATUS_IGANG = "igang"
STATUS_FAERDIG = "faerdig"

STATUS_CHOICES = [
    (STATUS_ONSKE, "Ønskede forbedringer"),
    (STATUS_REPARATION, "Nødvendige reparationer"),
    (STATUS_IGANG, "Igangværende"),
    (STATUS_FAERDIG, "Færdige"),
]


def sweep_finished_tickets():
    """Archive tickets that have sat in Færdige for 30+ days. Never deletes."""
    cutoff = timezone.now() - SWEEP_AFTER
    Ticket.objects.filter(status=STATUS_FAERDIG, archived=False, completed_at__lte=cutoff).update(
        archived=True, archived_at=timezone.now()
    )


class Ticket(models.Model):
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beskrivelse", blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_ONSKE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Oprettet af",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    created_at = models.DateTimeField("Oprettet", auto_now_add=True)
    updated_at = models.DateTimeField("Opdateret", auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def set_status(self, new_status):
        if new_status == STATUS_FAERDIG and self.status != STATUS_FAERDIG:
            self.completed_at = timezone.now()
        elif new_status != STATUS_FAERDIG:
            self.completed_at = None
        self.status = new_status

    def archive(self):
        self.archived = True
        self.archived_at = timezone.now()

    def reopen(self):
        self.archived = False
        self.archived_at = None
        if self.status == STATUS_FAERDIG:
            self.completed_at = timezone.now()


class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Fra",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_comments",
    )
    text = models.TextField("Kommentar")
    created_at = models.DateTimeField("Oprettet", auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author or 'Anonym'} on {self.ticket_id}"
