# Architecture

Ella is a private website for the people who share the boat *Ella*: a booking
calendar, a file archive and a maintenance board. It's a server-rendered
Django 5.2 app with Danish UI, used by about six people.

## Request path

```
browser
  │ HTTPS
  ▼
Cloudflare edge ─── TLS, "Always Use HTTPS", HSTS (ADR 0005)
  │                 No Access/Zero Trust in front any more (ADR 0010)
  │ Cloudflare Tunnel (outbound from the server; no open ports)
  ▼
cloudflared ──http──▶ Caddy ──http──▶ ella container :80
                     (shared,        gunicorn, 2 workers
                      all sites)     Invite link + password (ADR 0014)
                                     Login wall, public "/" (ADR 0006, 0012)
                                       │
                                       ▼
                              /data  ◀── bind mount ── /srv/state/ella
                              ├── db.sqlite3 (WAL)            (ADR 0003)
                              ├── media/filarkiv/<uuid>/…     uploads + miniature.jpg
                              └── backups/db.sqlite3          snapshot for restic
```

Everything to the left of the ella container belongs to the `home-server`
repo. This repo owns only the image.

## Components in this repo

| App | URL | What it does |
|---|---|---|
| `core` | `/`, `/healthz/` | Public front page and signed-in start page, placeholder pages, the login-wall middleware, the health check, `snapshot_db` |
| `adgang` | `/invitation/<token>/` | Single-use invitation links. The signup form lives on the link itself, which is the only way an account is created ([ADR 0014](adr/0014-invite-links-and-passwords.md)) |
| `booking` | `/kalender/` | Month/week/list calendar of trips; repeating trips are stored as separate rows sharing a `series_id` |
| `filarkiv` | `/filarkiv/` | Folders under two fixed roots, Billeder and Filer; upload, search, move and download files (max 25 MB). Pictures show as a thumbnail grid with a viewer ([ADR 0015](adr/0015-filarkiv-folders-and-inline-images.md)); everything is only reachable through logged-in views |
| `vedligehold` | `/vedligehold/` | Maintenance tickets on a board with comments; finished tickets archive themselves after 30 days |

All three feature apps record "who" as a foreign key to the signed-in
account, set by the view and absent from the forms
([ADR 0011](adr/0011-records-linked-to-accounts.md)). Templates render one
through the `person` filter in `core/templatetags/people.py`.

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
push to main ──▶ GitHub Actions: tests ──▶ build + push (inlined in build.yml;
                                             this repo is public and
                                             home-server is private, so its
                                             reusable workflow is unusable)
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
