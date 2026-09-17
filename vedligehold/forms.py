from django import forms

from .models import Comment, Ticket


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "status", "created_by"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "title": "Titel",
            "description": "Beskrivelse",
            "status": "Status",
            "created_by": "Oprettet af",
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["author", "text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3, "placeholder": "Skriv en kommentar…"}),
        }
        labels = {
            "author": "Fra",
            "text": "Kommentar",
        }

