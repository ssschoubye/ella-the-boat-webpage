import sqlite3
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from core.templatetags.people import person

User = get_user_model()


class HealthzTests(TestCase):
    def test_healthz_is_reachable_without_login(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")


class LoginWallTests(TestCase):
    def test_the_front_page_is_public(self):
        """ADR 0012. It is the only page that is."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/landing.html")

    def test_the_public_front_page_offers_a_way_in(self):
        response = self.client.get("/")
        self.assertContains(response, "/login/")

    def test_the_public_front_page_leaks_no_private_pages(self):
        response = self.client.get("/")
        for private in ("/kalender/", "/filarkiv/", "/vedligehold/"):
            with self.subTest(path=private):
                self.assertNotContains(response, private)

    def test_every_other_page_requires_login(self):
        for path in ("/kalender/", "/filarkiv/", "/vedligehold/", "/logbog/", "/skader/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login/", response["Location"])

    def test_signing_in_replaces_the_landing_page_with_the_real_start_page(self):
        self.client.force_login(User.objects.create_user("anton"))

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")

    def test_the_login_page_asks_for_an_email_and_a_password(self):
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'type="password"')

    def test_the_login_page_does_not_offer_self_service_signup(self):
        """An invitation link is the only way in (ADR 0014)."""
        response = self.client.get("/login/")

        self.assertNotContains(response, "/signup/")
        self.assertNotContains(response, "/invitation/")


class PersonFilterTests(TestCase):
    def test_it_prefers_the_first_name_from_google(self):
        user = User.objects.create_user("anton-abc", email="anton@example.com", first_name="Anton")
        self.assertEqual(person(user), "Anton")

    def test_it_falls_back_to_the_email_local_part(self):
        user = User.objects.create_user("x-abc", email="kathrine@example.com")
        self.assertEqual(person(user), "kathrine")

    def test_it_falls_back_to_the_username(self):
        self.assertEqual(person(User.objects.create_user("lastresort")), "lastresort")

    def test_a_deleted_account_reads_as_unknown(self):
        """booker/uploaded_by are SET_NULL, so this is a real case."""
        self.assertEqual(person(None), "Ukendt")


class SnapshotDbTests(TestCase):
    def test_writes_a_readable_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "db.sqlite3"
            with sqlite3.connect(live) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE t (x INTEGER)")
                db.execute("INSERT INTO t VALUES (42)")
            db.close()

            with mock.patch.dict(connection.settings_dict, {"NAME": str(live)}):
                call_command("snapshot_db", stdout=StringIO())

            snapshot = Path(tmp) / "backups" / "db.sqlite3"
            self.assertTrue(snapshot.is_file())
            self.assertFalse(snapshot.with_name("db.sqlite3.tmp").exists())
            copy = sqlite3.connect(snapshot)
            try:
                self.assertEqual(copy.execute("SELECT x FROM t").fetchone(), (42,))
                self.assertEqual(copy.execute("PRAGMA journal_mode").fetchone(), ("delete",))
            finally:
                copy.close()
