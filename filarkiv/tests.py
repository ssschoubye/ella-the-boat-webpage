import shutil
import tempfile
from io import BytesIO, StringIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import ArchiveFile, Folder

User = get_user_model()

MEDIA_ROOT = tempfile.mkdtemp()


def png_bytes(size=(1200, 800)):
    buffer = BytesIO()
    Image.new("RGB", size, "navy").save(buffer, "PNG")
    return buffer.getvalue()


def billeder():
    return Folder.objects.get(root_key=Folder.BILLEDER)


def filer():
    return Folder.objects.get(root_key=Folder.FILER)


class MediaTestCase(TestCase):
    """Uploads must not land in the real media directory during a test run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = override_settings(MEDIA_ROOT=tempfile.mkdtemp(dir=MEDIA_ROOT))
        cls._media.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media.disable()
        super().tearDownClass()

    def setUp(self):
        self.anton = User.objects.create_user("anton", first_name="Anton")
        self.client.force_login(self.anton)

    def make_file(self, name="forsikring.txt", content=b"papirer", folder=None):
        archive_file = ArchiveFile(title=name, folder=folder or filer())
        archive_file.file.save(name, ContentFile(content), save=True)
        return archive_file

    def upload(self, name="forsikring.txt", content=b"papirer", folder=None, **extra):
        return self.client.post(
            reverse("filarkiv_upload"),
            {
                "file": SimpleUploadedFile(name, content),
                "folder": (folder or filer()).pk,
                "title": "Forsikring",
                "description": "",
                **extra,
            },
        )


class UploaderAttributionTests(MediaTestCase):
    """uploaded_by is the signed-in account, not a self-declared label."""

    def setUp(self):
        super().setUp()
        self.someone_else = User.objects.create_user("emil", first_name="Emil")

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


class UploadIntoFolderTests(MediaTestCase):
    def test_the_upload_lands_in_the_chosen_folder_and_returns_there(self):
        sommer = Folder.objects.create(name="Sommertur", parent=billeder())

        response = self.upload(folder=sommer)

        self.assertEqual(ArchiveFile.objects.get().folder, sommer)
        self.assertRedirects(response, reverse("filarkiv_folder", args=[sommer.pk]))

    def test_a_folder_is_required(self):
        response = self.client.post(
            reverse("filarkiv_upload"),
            {"file": SimpleUploadedFile("a.txt", b"a"), "folder": "", "title": "", "description": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ArchiveFile.objects.exists())

    def test_the_folder_in_the_query_string_is_preselected(self):
        response = self.client.get(reverse("filarkiv_upload") + f"?mappe={billeder().pk}")

        self.assertContains(response, f'<option value="{billeder().pk}" selected>Billeder</option>', html=True)

    def test_the_folder_choices_show_the_full_path(self):
        Folder.objects.create(name="2026", parent=billeder())

        response = self.client.get(reverse("filarkiv_upload"))

        self.assertContains(response, "Billeder / 2026")


class ThumbnailTests(MediaTestCase):
    def test_uploading_an_image_makes_a_small_thumbnail(self):
        self.upload("havn.png", png_bytes(), folder=billeder())

        archive_file = ArchiveFile.objects.get()
        self.assertTrue(archive_file.thumbnail)
        with archive_file.thumbnail.open("rb") as fh, Image.open(fh) as thumb:
            self.assertEqual(thumb.format, "JPEG")
            self.assertLessEqual(max(thumb.size), 480)

    def test_an_unreadable_image_uploads_without_a_thumbnail(self):
        response = self.upload("broken.jpg", b"not a jpeg", folder=billeder())

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ArchiveFile.objects.get().thumbnail)

    def test_a_document_gets_no_thumbnail(self):
        self.upload("manual.pdf", b"%PDF-1.4")

        self.assertFalse(ArchiveFile.objects.get().thumbnail)

    def test_the_backfill_command_makes_missing_thumbnails(self):
        archive_file = self.make_file("havn.png", png_bytes(), folder=billeder())

        call_command("make_thumbnails", stdout=StringIO())

        archive_file.refresh_from_db()
        self.assertTrue(archive_file.thumbnail)

    def test_deleting_a_file_removes_its_thumbnail_from_disk(self):
        self.upload("havn.png", png_bytes(), folder=billeder())
        archive_file = ArchiveFile.objects.get()
        storage, file_name, thumb_name = archive_file.file.storage, archive_file.file.name, archive_file.thumbnail.name

        self.client.post(reverse("filarkiv_delete", args=[archive_file.pk]))

        self.assertFalse(storage.exists(file_name))
        self.assertFalse(storage.exists(thumb_name))


class InlineViewingTests(MediaTestCase):
    def test_an_image_is_served_inline_and_locked_down(self):
        archive_file = self.make_file("havn.png", png_bytes(), folder=billeder())

        response = self.client.get(reverse("filarkiv_view", args=[archive_file.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response["Content-Disposition"].startswith("inline"))
        self.assertEqual(response["Content-Security-Policy"], "default-src 'none'; sandbox")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_svg_and_other_files_are_never_served_inline(self):
        for name in ("tegning.svg", "side.html", "forsikring.txt"):
            with self.subTest(name=name):
                archive_file = self.make_file(name, b"<svg onload=alert(1)>")
                response = self.client.get(reverse("filarkiv_view", args=[archive_file.pk]))
                self.assertEqual(response.status_code, 404)

    def test_download_is_still_an_attachment(self):
        archive_file = self.make_file("havn.png", png_bytes(), folder=billeder())

        response = self.client.get(reverse("filarkiv_download", args=[archive_file.pk]))

        self.assertTrue(response["Content-Disposition"].startswith("attachment"))

    def test_the_thumbnail_is_served_inline_as_jpeg(self):
        self.upload("havn.png", png_bytes(), folder=billeder())
        archive_file = ArchiveFile.objects.get()

        response = self.client.get(reverse("filarkiv_thumbnail", args=[archive_file.pk]))

        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertEqual(response["Content-Security-Policy"], "default-src 'none'; sandbox")

    def test_a_missing_thumbnail_is_a_404(self):
        archive_file = self.make_file("broken.jpg", b"nope", folder=billeder())

        response = self.client.get(reverse("filarkiv_thumbnail", args=[archive_file.pk]))

        self.assertEqual(response.status_code, 404)

    def test_both_inline_urls_are_behind_the_login_wall(self):
        archive_file = self.make_file("havn.png", png_bytes(), folder=billeder())
        self.client.logout()

        for name in ("filarkiv_view", "filarkiv_thumbnail"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=[archive_file.pk]))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response["Location"])

    def test_the_folder_page_shows_images_as_a_grid_and_documents_as_a_list(self):
        picture = self.make_file("havn.png", png_bytes(), folder=billeder())
        document = self.make_file("manual.pdf", b"%PDF", folder=billeder())

        response = self.client.get(reverse("filarkiv_folder", args=[billeder().pk]))

        self.assertContains(response, f'data-full="{reverse("filarkiv_view", args=[picture.pk])}"')
        self.assertNotContains(response, f'data-full="{reverse("filarkiv_view", args=[document.pk])}"')
        self.assertContains(response, reverse("filarkiv_download", args=[document.pk]))
        self.assertContains(response, "js/lightbox.js")


class FolderTests(MediaTestCase):
    def test_the_root_page_shows_only_the_two_fixed_folders(self):
        Folder.objects.create(name="2026", parent=billeder())

        response = self.client.get(reverse("filarkiv"))

        self.assertContains(response, 'class="archive__folder"', count=2)

    def test_the_path_links_every_folder_above_and_shows_the_current_one_as_text(self):
        sommer = Folder.objects.create(name="Sommertur", parent=billeder())
        dag = Folder.objects.create(name="Dag 1", parent=sommer)

        response = self.client.get(reverse("filarkiv_folder", args=[dag.pk]))

        self.assertContains(response, f'<a href="{reverse("filarkiv")}">Filarkiv</a>', html=True)
        self.assertContains(response, f'<a href="{reverse("filarkiv_folder", args=[billeder().pk])}">Billeder</a>', html=True)
        self.assertContains(response, f'<a href="{reverse("filarkiv_folder", args=[sommer.pk])}">Sommertur</a>', html=True)
        self.assertContains(response, '<span aria-current="page">Dag 1</span>', html=True)

    def test_the_up_arrow_goes_to_the_parent_folder(self):
        sommer = Folder.objects.create(name="Sommertur", parent=billeder())

        response = self.client.get(reverse("filarkiv_folder", args=[sommer.pk]))

        self.assertContains(response, f'class="archive__up" href="{reverse("filarkiv_folder", args=[billeder().pk])}"')

    def test_the_up_arrow_on_a_root_folder_goes_to_the_archive_start(self):
        response = self.client.get(reverse("filarkiv_folder", args=[billeder().pk]))

        self.assertContains(response, f'class="archive__up" href="{reverse("filarkiv")}"')

    def test_creating_a_subfolder(self):
        response = self.client.post(reverse("filarkiv_folder_create", args=[billeder().pk]), {"name": " Sommertur "})

        sommer = Folder.objects.get(name="Sommertur")
        self.assertEqual(sommer.parent, billeder())
        self.assertRedirects(response, reverse("filarkiv_folder", args=[sommer.pk]))

    def test_two_folders_in_the_same_place_cannot_share_a_name(self):
        Folder.objects.create(name="Sommertur", parent=billeder())

        response = self.client.post(reverse("filarkiv_folder_create", args=[billeder().pk]), {"name": "sommertur"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Folder.objects.filter(name__iexact="sommertur").count(), 1)

    def test_the_same_name_is_fine_in_another_folder(self):
        Folder.objects.create(name="2026", parent=billeder())

        self.client.post(reverse("filarkiv_folder_create", args=[filer().pk]), {"name": "2026"})

        self.assertEqual(Folder.objects.filter(name="2026").count(), 2)

    def test_renaming_a_folder(self):
        sommer = Folder.objects.create(name="Sommer", parent=billeder())

        self.client.post(reverse("filarkiv_folder_rename", args=[sommer.pk]), {"name": "Sommertur"})

        sommer.refresh_from_db()
        self.assertEqual(sommer.name, "Sommertur")

    def test_the_root_folders_cannot_be_renamed(self):
        response = self.client.post(reverse("filarkiv_folder_rename", args=[billeder().pk]), {"name": "Fotos"})

        self.assertRedirects(response, reverse("filarkiv_folder", args=[billeder().pk]))
        self.assertTrue(Folder.objects.filter(root_key=Folder.BILLEDER, name="Billeder").exists())

    def test_the_root_folders_cannot_be_deleted(self):
        self.anton.is_staff = True
        self.anton.save()

        response = self.client.post(reverse("filarkiv_folder_delete", args=[filer().pk]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Folder.objects.filter(root_key=Folder.FILER).exists())

    def test_deleting_an_empty_folder(self):
        sommer = Folder.objects.create(name="Sommertur", parent=billeder())

        response = self.client.post(reverse("filarkiv_folder_delete", args=[sommer.pk]))

        self.assertRedirects(response, reverse("filarkiv_folder", args=[billeder().pk]))
        self.assertFalse(Folder.objects.filter(pk=sommer.pk).exists())

    def test_a_folder_with_contents_cannot_be_deleted_by_a_non_admin(self):
        sommer = Folder.objects.create(name="Sommertur", parent=billeder())
        Folder.objects.create(name="Dag 1", parent=sommer)

        response = self.client.post(reverse("filarkiv_folder_delete", args=[sommer.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Folder.objects.filter(parent=sommer).count(), 1)

    def test_a_non_admin_is_not_offered_the_delete_button_on_a_full_folder(self):
        sommer = Folder.objects.create(name="Sommertur", parent=billeder())
        self.make_file("havn.png", png_bytes(), folder=sommer)

        response = self.client.get(reverse("filarkiv_folder", args=[sommer.pk]))

        self.assertNotContains(response, reverse("filarkiv_folder_delete", args=[sommer.pk]))
        self.assertContains(response, "kun slettes, når den er tom")

    def test_an_admin_deletes_a_folder_with_everything_in_it(self):
        self.anton.is_staff = True
        self.anton.save()
        sommer = Folder.objects.create(name="Sommertur", parent=billeder())
        dag = Folder.objects.create(name="Dag 1", parent=sommer)
        self.upload("havn.png", png_bytes(), folder=dag)
        self.upload("plan.txt", b"plan", folder=sommer)
        stored = [name for f in ArchiveFile.objects.all() for name in (f.file.name, f.thumbnail.name) if name]
        storage = ArchiveFile.objects.first().file.storage
        kept = self.make_file("anden.txt", b"bliver", folder=filer())

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("filarkiv_folder_delete", args=[sommer.pk]))

        self.assertRedirects(response, reverse("filarkiv_folder", args=[billeder().pk]))
        self.assertFalse(Folder.objects.filter(pk__in=[sommer.pk, dag.pk]).exists())
        self.assertEqual(list(ArchiveFile.objects.all()), [kept])
        self.assertEqual(len(stored), 3)
        for name in stored:
            self.assertFalse(storage.exists(name), name)
        self.assertTrue(storage.exists(kept.file.name))

    def test_moving_a_file_to_another_folder(self):
        archive_file = self.make_file("havn.png", png_bytes(), folder=filer())

        response = self.client.post(
            reverse("filarkiv_edit", args=[archive_file.pk]),
            {"title": "Havnen", "folder": billeder().pk, "description": ""},
        )

        archive_file.refresh_from_db()
        self.assertEqual(archive_file.folder, billeder())
        self.assertEqual(archive_file.title, "Havnen")
        self.assertRedirects(response, reverse("filarkiv_folder", args=[billeder().pk]))

    def test_search_covers_every_folder_and_shows_the_path(self):
        dag = Folder.objects.create(name="Dag 1", parent=Folder.objects.create(name="Sommertur", parent=billeder()))
        self.make_file("ankerplads.png", png_bytes(), folder=dag)

        response = self.client.get(reverse("filarkiv"), {"q": "anker"})

        self.assertContains(response, "Billeder / Sommertur / Dag 1")


class RootFolderMigrationTests(TransactionTestCase):
    """0006 sorts the files that exist before folders into Billeder and Filer."""

    # The flush after this test would otherwise wipe the root folders the
    # other test cases rely on.
    serialized_rollback = True

    before = [("filarkiv", "0005_folder_and_thumbnail")]
    after = [("filarkiv", "0006_root_folders")]

    def tearDown(self):
        # Leave the schema at the latest migration for the tests that follow.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_images_go_to_billeder_and_the_rest_to_filer(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old_apps = executor.loader.project_state(self.before).apps
        OldFile = old_apps.get_model("filarkiv", "ArchiveFile")
        OldFile.objects.create(title="Havn", file="filarkiv/a/havn.JPG")
        OldFile.objects.create(title="Manual", file="filarkiv/b/manual.pdf")
        OldFile.objects.create(title="Tegning", file="filarkiv/c/tegning.svg")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)
        new_apps = executor.loader.project_state(self.after).apps
        NewFile = new_apps.get_model("filarkiv", "ArchiveFile")

        folders = dict(NewFile.objects.values_list("title", "folder__root_key"))
        self.assertEqual(folders, {"Havn": "billeder", "Manual": "filer", "Tegning": "filer"})


def tearDownModule():
    shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
