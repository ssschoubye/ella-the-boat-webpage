from django import forms

from .models import Booking, REPEAT_CHOICES

DATETIME_LOCAL_FORMAT = "%Y-%m-%dT%H:%M"


class BookingForm(forms.ModelForm):
    start_date = forms.DateTimeField(
        label="Startdato",
        widget=forms.DateTimeInput(attrs={"class": "js-datetime-picker"}, format=DATETIME_LOCAL_FORMAT),
        input_formats=[DATETIME_LOCAL_FORMAT],
    )
    end_date = forms.DateTimeField(
        label="Slutdato",
        widget=forms.DateTimeInput(attrs={"class": "js-datetime-picker"}, format=DATETIME_LOCAL_FORMAT),
        input_formats=[DATETIME_LOCAL_FORMAT],
    )
    repeat_type = forms.ChoiceField(
        label="Gentag",
        choices=REPEAT_CHOICES,
        required=False,
        initial="none",
    )
    repeat_count = forms.IntegerField(
        label="Antal gange",
        required=False,
        min_value=2,
        max_value=52,
        initial=4,
        help_text="Inklusiv den første tur.",
    )

    class Meta:
        model = Booking
        fields = ["title", "booker", "start_date", "end_date", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "title": "Titel",
            "booker": "Booker",
            "notes": "Noter",
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "Slutdato kan ikke ligge før startdato.")

        repeat_type = cleaned_data.get("repeat_type")
        if repeat_type and repeat_type != "none" and not cleaned_data.get("repeat_count"):
            self.add_error("repeat_count", "Angiv hvor mange gange turen skal gentages.")
        return cleaned_data
