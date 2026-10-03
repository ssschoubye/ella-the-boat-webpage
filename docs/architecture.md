# Architecture

Ella is a private website for the people who share the boat *Ella*: a booking
calendar, a file archive and a maintenance board. It's a server-rendered
Django 5.2 app with Danish UI, used by about six people.

## Request path

```
browser
  │ HTTPS
  ▼
Cloudflare edge ─── Cloudflare Access: email one-time PIN (ADR 0007)
  │                 TLS, "Always Use HTTPS", HSTS (ADR 0005)
  │ Cloudflare Tunnel (outbound from the server; no open ports)
  ▼
cloudflared ──http──▶ Caddy ──http──▶ ella container :80
                     (shared,        gunicorn, 2 workers
                      all sites)     Django login wall (ADR 0006)
                                       │
                                       ▼
                              /data  ◀── bind mount ── /srv/state/ella
                              ├── db.sqlite3 (WAL)            (ADR 0003)
                              ├── media/filarkiv/<uuid>/…     uploads
                              └── backups/db.sqlite3          snapshot for restic
```

Everything to the left of the ella container belongs to the `home-server`
repo. This repo owns only the image.

## Components in this repo

| App | URL | What it does |
|---|---|---|
| `core` | `/`, `/healthz/` | Home page, placeholder pages, the login-wall middleware, the health check, `snapshot_db` |
| `booking` | `/kalender/` | Month/week/list calendar of trips; repeating trips are stored as separate rows sharing a `series_id` |
| `filarkiv` | `/filarkiv/` | Upload, search and download files (max 25 MB); only downloadable through a logged-in view |
| `vedligehold` | `/vedligehold/` | Maintenance tickets on a board with comments; finished tickets archive themselves after 30 days |

All three feature apps record "who" by picking from the hardcoded
`BOOKER_CHOICES` list, not the logged-in account
([ADR 0008](adr/0008-records-are-not-linked-to-user-accounts.md)).

## Settings

| Module | Used by | Database | Static files |
|---|---|---|---|
| `config.settings.dev` | `manage.py` (default) | `./db.sqlite3` | Django's dev server |
| `config.settings.prod` | the Docker image | `$DJANGO_DATA_DIR/db.sqlite3` | WhiteNoise, collected at build ([ADR 0004](adr/0004-serve-static-files-with-whitenoise.md)) |

Production configuration comes from environment variables. Only
`DJANGO_SECRET_KEY` has to be set; the rest default to the home-server
values. See [deployment.md](deployment.md#what-the-image-does).

## Build and release

```
push to main ──▶ GitHub Actions: tests ──▶ home-server's build-site-image.yml
                                             └─▶ ghcr.io/ssschoubye/ella:sha-<short>
home-server: pin tag in group_vars ──▶ commit ──▶ make deploy SERVICE=ella
container start: chown /data ──▶ drop to uid 10001 ──▶ migrate ──▶ gunicorn
```

There's no `latest` tag and nothing updates automatically. The commit in
home-server that bumps the tag is the deploy record
([ADR 0002](adr/0002-run-as-a-container-on-the-home-server.md)).

## Backups

Restic on the home server backs up `/srv/state` nightly at 03:30. A pre-backup
hook runs `manage.py snapshot_db` in the container first. Restic backs up the
snapshot and `media/`, and excludes the live database files
([ADR 0003](adr/0003-sqlite-on-a-bind-mount-with-snapshot-backups.md)).

## Limits worth knowing

- One container and one SQLite writer at a time. Fine for this group; see
  ADR 0003 for what changes if that stops being true.
- Uploads are capped at 25 MB by the form, well under Cloudflare's 100 MB
  request limit on the free plan.
- The site is only as available as the home server (a laptop on Wi-Fi).
