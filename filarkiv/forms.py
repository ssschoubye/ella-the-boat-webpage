from pathlib import Path

from django import forms

from .models import ArchiveFile

MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB


class ArchiveFileForm(forms.ModelForm):
    class Meta:
        model = ArchiveFile
        fields = ["file", "title", "uploaded_by", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "file": "Fil",
            "title": "Titel",
            "uploaded_by": "Uploadet af",
            "description": "Beskrivelse",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > MAX_UPLOAD_SIZE:
            raise forms.ValidationError("Filen er for stor (maks. 25 MB).")
        return file

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.title:
            instance.title = Path(instance.file.name).stem
        if commit:
            instance.save()
        return instance
