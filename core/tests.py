import sqlite3
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.db import connection
from django.test import TestCase


class HealthzTests(TestCase):
    def test_healthz_is_reachable_without_login(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_other_pages_still_require_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])


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
