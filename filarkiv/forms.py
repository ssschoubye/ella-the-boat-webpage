from pathlib import Path

from django import forms

from .models import ArchiveFile, Folder, folder_paths

MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB


class _PathOrderedChoices(forms.models.ModelChoiceIterator):
    """Folders listed by full path ("Billeder / 2026"), in path order."""

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        paths = folder_paths()
        for folder in sorted(self.queryset, key=lambda f: paths[f.pk].lower()):
            yield (forms.models.ModelChoiceIteratorValue(self.field.prepare_value(folder), folder), paths[folder.pk])


class FolderChoiceField(forms.ModelChoiceField):
    iterator = _PathOrderedChoices

    def __init__(self, **kwargs):
        super().__init__(queryset=Folder.objects.all(), label="Mappe", empty_label="Vælg mappe", **kwargs)


class ArchiveFileForm(forms.ModelForm):
    folder = FolderChoiceField()

    class Meta:
        model = ArchiveFile
        # No "uploaded_by": the view sets it from the session (ADR 0011).
        fields = ["file", "folder", "title", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "file": "Fil",
            "title": "Titel",
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


class ArchiveFileEditForm(forms.ModelForm):
    folder = FolderChoiceField()

    class Meta:
        model = ArchiveFile
        fields = ["title", "folder", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "title": "Titel",
            "description": "Beskrivelse",
        }


class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ["name"]
        labels = {"name": "Navn"}

    def __init__(self, *args, parent, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        siblings = Folder.objects.filter(parent=self.parent, name__iexact=name).exclude(pk=self.instance.pk)
        if siblings.exists():
            raise forms.ValidationError("Der findes allerede en mappe med det navn her.")
        return name
