import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ArchiveFile

User = get_user_model()


# Uploads must not land in the real media directory during a test run.
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class UploaderAttributionTests(TestCase):
    """uploaded_by is the signed-in account, not a self-declared label."""

    def setUp(self):
        self.anton = User.objects.create_user("anton", first_name="Anton")
        self.someone_else = User.objects.create_user("emil", first_name="Emil")
        self.client.force_login(self.anton)

    def tearDown(self):
        for archive_file in ArchiveFile.objects.all():
            archive_file.file.delete(save=False)

    def upload(self, **extra):
        return self.client.post(
            reverse("filarkiv_upload"),
            {
                "file": SimpleUploadedFile("forsikring.txt", b"papirer"),
                "title": "Forsikring",
                "description": "",
                **extra,
            },
        )

    def test_the_uploader_is_the_signed_in_user(self):
        self.upload()

        self.assertEqual(ArchiveFile.objects.get().uploaded_by, self.anton)

    def test_a_posted_uploader_is_ignored(self):
        self.upload(uploaded_by=self.someone_else.pk)

        self.assertEqual(ArchiveFile.objects.get().uploaded_by, self.anton)

    def test_the_form_has_no_uploader_field(self):
        response = self.client.get(reverse("filarkiv_upload"))
        self.assertNotContains(response, 'name="uploaded_by"')

    def test_a_missing_title_still_falls_back_to_the_filename(self):
        """Guarding the form's own save(), which the view now calls with
        commit=False in order to set the uploader."""
        self.upload(title="")

        self.assertEqual(ArchiveFile.objects.get().title, "forsikring")
