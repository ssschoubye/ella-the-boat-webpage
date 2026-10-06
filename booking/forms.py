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
        # 1 is what the form shows for "Gentager ikke"; a repeat needs at
        # least 2, which clean() checks.
        min_value=1,
        max_value=52,
        initial=1,
        help_text="Inklusiv den første tur.",
    )

    class Meta:
        model = Booking
        # No "booker" field: the view sets it to whoever is signed in, so
        # nobody picks their own name off a list any more (ADR 0011).
        fields = ["title", "start_date", "end_date", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "title": "Titel",
            "notes": "Noter",
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "Slutdato kan ikke ligge før startdato.")

        repeat_type = cleaned_data.get("repeat_type")
        repeat_count = cleaned_data.get("repeat_count")
        if repeat_type and repeat_type != "none":
            if not repeat_count:
                self.add_error("repeat_count", "Angiv hvor mange gange turen skal gentages.")
            elif repeat_count < 2:
                self.add_error("repeat_count", "En gentagende tur skal forekomme mindst 2 gange.")
        else:
            # Whatever was typed, a trip that doesn't repeat happens once.
            cleaned_data["repeat_count"] = 1
        return cleaned_data
