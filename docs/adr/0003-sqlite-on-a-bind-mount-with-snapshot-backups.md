# 0003. SQLite on a bind mount, with snapshot backups

- **Status:** Accepted
- **Date:** 2026-10-03

## Context
Ella needs a database and somewhere to keep uploaded files. The home-server
stack had been set up for a stateless site. The home server keeps all state
under `/srv/state/<stack>/`, and restic backs up all of `/srv/state` nightly.
It runs every executable in `/etc/home-server/backup-pre.d/` first and aborts
the backup if one fails. Restic also excludes `*.tmp`.

The site has about six users and very little write traffic. The owner may
host other projects with their own databases later.

## Decision
Use **SQLite** in production, stored with the uploads under `DJANGO_DATA_DIR`
(`/data` in the container, bind-mounted from `/srv/state/ella`):
- The SQLite connection uses WAL mode, `synchronous=NORMAL`,
  `transaction_mode=IMMEDIATE` and a 20-second busy timeout. This avoids
  "database is locked" errors between gunicorn workers.
- `manage.py snapshot_db` copies the live DB to `/data/backups/db.sqlite3`
  using SQLite's online backup API. It writes to a `.tmp` file, renames it
  into place, and switches the copy to rollback-journal mode so the snapshot
  is a single self-contained file.
- A restic pre-backup hook in home-server runs `snapshot_db` before each
  backup. If the container isn't running, it exits 0 and keeps the previous
  snapshot, so ella being down never blocks the server's other backups.
- Restic excludes the live `db.sqlite3*` files and backs up the snapshot plus
  `media/`.
- The entrypoint `chown`s `/data` as root, because home-server re-creates the
  directory as `root:root` on every deploy and restored files are root-owned.
  It then drops to uid 10001.

## Consequences
- No extra container, password or dump tooling. Restore means copying one file
  back ([deployment.md](../deployment.md#restoring-the-database)).
- Only one writer at a time, and only one app container. Both are fine at this
  scale.
- A backup could be up to a day old, which is acceptable here. Recovery is
  always to the last snapshot, never a torn live file.
- Moving to Postgres later means a `dumpdata`/`loaddata` migration, which is a
  bounded amount of work.
- Future projects are unaffected. Each SQLite database is private to its app,
  and a shared Postgres would be its own home-server stack, built the same
  way whatever ella uses.

## Alternatives considered
- **Postgres container in the ella stack:** handles concurrency better, but adds
  a container, a secret, a `pg_dump` hook and major-version upgrades, all for
  six users.
- **Shared Postgres for all future projects:** a reasonable future step, but
  ella shouldn't be the reason to build it now.
- **Backing up the live SQLite file directly:** simplest, but restic can copy
  it mid-write and produce a corrupt backup.
