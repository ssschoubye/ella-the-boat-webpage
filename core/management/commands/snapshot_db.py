import os
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "Write a consistent copy of the SQLite database for backups. "
        "The home server's restic pre-backup hook runs this, then backs up the copy "
        "instead of the live file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            help="Where to write the snapshot. Defaults to backups/db.sqlite3 next to the database.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError(f"snapshot_db only supports SQLite, not {connection.vendor}.")

        source = Path(connection.settings_dict["NAME"])
        if not source.is_file():
            raise CommandError(f"No database file at {source}.")

        output = Path(options["output"]) if options["output"] else source.parent / "backups" / "db.sqlite3"
        output.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temp file and rename, so a backup never sees a half-written
        # snapshot. restic excludes *.tmp.
        tmp = output.with_name(output.name + ".tmp")
        tmp.unlink(missing_ok=True)

        src = sqlite3.connect(source)
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
            # The copy inherits WAL mode; make it a single self-contained file.
            # The app switches it back to WAL on its first connection after a restore.
            dst.execute("PRAGMA journal_mode=DELETE")
        finally:
            dst.close()
            src.close()
        os.replace(tmp, output)

        self.stdout.write(f"Snapshot written to {output}")
