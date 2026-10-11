import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

# The only types served inline (ADR 0015). Everything else, SVG included, is
# download-only, because an inline SVG or HTML file could run script.
IMAGE_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def is_image_name(name):
    return Path(name).suffix.lstrip(".").lower() in IMAGE_CONTENT_TYPES


def archive_upload_path(instance, filename):
    return f"filarkiv/{uuid.uuid4().hex}/{filename}"


def thumbnail_upload_path(instance, filename):
    # Next to the original, in its random directory.
    return f"{Path(instance.file.name).parent.as_posix()}/{filename}"


class Folder(models.Model):
    BILLEDER = "billeder"
    FILER = "filer"

    name = models.CharField("Navn", max_length=100)
    parent = models.ForeignKey(
        "self",
        verbose_name="Overmappe",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    # Set only on the two fixed top-level folders, Billeder and Filer.
    root_key = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    created_at = models.DateTimeField("Oprettet", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "mappe"
        verbose_name_plural = "mapper"
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="filarkiv_folder_unique_name_per_parent"),
            # The pair above says nothing about the top level: two NULL
            # parents are distinct in SQL, so without this a third root
            # folder is possible. root_key would be empty on it, which makes
            # is_root False, which makes it renameable and deletable.
            models.UniqueConstraint(
                fields=["name"], condition=models.Q(parent=None), name="filarkiv_folder_unique_root_name"
            ),
        ]

    def __str__(self):
        return " / ".join(f.name for f in self.ancestors())

    @property
    def is_root(self):
        return self.root_key is not None

    def ancestors(self):
        """The path from the top-level folder down to this one, inclusive.

        Stops if it ever meets the same folder twice. clean() rejects a cycle,
        but this walk is on the folder page and in the admin changelist, and a
        row written around validation must not be able to spin a worker
        forever.
        """
        chain = []
        seen = set()
        folder = self
        while folder is not None and folder.pk not in seen:
            seen.add(folder.pk)
            chain.append(folder)
            folder = folder.parent
        return chain[::-1]

    @staticmethod
    def has_sibling_named(parent, name, exclude_pk=None):
        """Is there already a folder of this name in `parent`?

        Compared casefolded in Python: SQLite's iexact only folds ASCII and
        the unique constraint is case-sensitive, so neither catches Æbler
        against æbler -- and Danish names are the normal case here.
        """
        siblings = Folder.objects.filter(parent=parent)
        if exclude_pk is not None:
            siblings = siblings.exclude(pk=exclude_pk)
        folded = name.strip().casefold()
        return any(sibling.name.casefold() == folded for sibling in siblings)

    def clean(self):
        super().clean()
        if self.parent_id is None:
            # Billeder and Filer are made by migration 0006 and are the only
            # folders that belong at the top level.
            if not self.is_root:
                raise ValidationError({"parent": "Vælg en overmappe. Kun Billeder og Filer ligger øverst."})
            return

        parent = Folder.objects.filter(pk=self.parent_id).first()
        if parent is None:
            return
        if self.pk is not None and self.pk in {f.pk for f in parent.ancestors()}:
            raise ValidationError(
                {"parent": "En mappe kan ikke ligge i sig selv eller i en af sine egne undermapper."}
            )
        if self.has_sibling_named(self.parent_id, self.name, exclude_pk=self.pk):
            raise ValidationError({"name": "Der findes allerede en mappe med det navn her."})

    def is_empty(self):
        return not self.children.exists() and not self.files.exists()

    def subtree(self):
        """This folder and every folder below it, parents before children."""
        children_of = {}
        for pk, parent_id in Folder.objects.values_list("pk", "parent_id"):
            children_of.setdefault(parent_id, []).append(pk)
        pks = [self.pk]
        for pk in pks:
            pks.extend(children_of.get(pk, []))
        folders = Folder.objects.in_bulk(pks)
        return [folders[pk] for pk in pks]


def folder_paths():
    """{pk: "Billeder / 2026 / Sommertur"} for every folder, in one query."""
    folders = {f.pk: f for f in Folder.objects.only("pk", "name", "parent_id")}
    paths = {}

    def path(pk):
        if pk not in paths:
            folder = folders[pk]
            prefix = f"{path(folder.parent_id)} / " if folder.parent_id else ""
            paths[pk] = prefix + folder.name
        return paths[pk]

    for pk in folders:
        path(pk)
    return paths


class ArchiveFile(models.Model):
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beskrivelse", blank=True)
    file = models.FileField("Fil", upload_to=archive_upload_path)
    thumbnail = models.FileField("Miniature", upload_to=thumbnail_upload_path, blank=True, editable=False)
    folder = models.ForeignKey(
        Folder,
        verbose_name="Mappe",
        on_delete=models.PROTECT,
        related_name="files",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Uploadet af",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploads",
    )
    uploaded_at = models.DateTimeField("Uploadet", auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return Path(self.file.name).name

    @property
    def extension(self):
        return Path(self.file.name).suffix.lstrip(".").upper()

    @property
    def is_image(self):
        return is_image_name(self.file.name)

    @property
    def content_type(self):
        return IMAGE_CONTENT_TYPES.get(self.extension.lower())

    def delete_stored_files(self):
        """Remove the upload and its thumbnail from disk."""
        self.file.delete(save=False)
        self.thumbnail.delete(save=False)
