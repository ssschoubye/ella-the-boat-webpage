from django import forms

from .models import Comment, Ticket


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        # No "created_by"/"author": the views set them from the session
        # (ADR 0011).
        fields = ["title", "description", "status"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "title": "Titel",
            "description": "Beskrivelse",
            "status": "Status",
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3, "placeholder": "Skriv en kommentar…"}),
        }
        labels = {
            "text": "Kommentar",
        }

