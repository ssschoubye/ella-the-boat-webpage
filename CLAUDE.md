# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A small, private Django 5.2 site for a group of people who share a boat ("Ella"). All user-facing text, URL paths, and model/field labels are in **Danish** — keep new UI text and URL slugs in Danish to match (e.g. `kalender/`, `tilfoj/`, `rediger/`, `slet/`).

## Commands

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env                             # defaults work for local dev

python manage.py migrate
python manage.py runserver
python manage.py makemigrations <app>

python manage.py test                            # all tests
python manage.py test booking                    # one app
python manage.py test booking.tests.SomeTestCase.test_method   # single test

docker build -t ella:test .                      # production image (see docs/deployment.md to run it)
```

`manage.py` defaults to `config.settings.dev` (SQLite, DEBUG=True). There is no linter config. Tests live in `core`, `adgang`, `booking`, `filarkiv` and `vedligehold`.

Sign-on needs no setup to work locally: `manage.py invite "Dig selv"` prints a link, and opening it creates an account. No provider, no SMTP, no secrets.

## Documentation

`docs/` holds architecture, deployment, security/sign-on and operations docs (index: `docs/README.md`). Decisions are recorded as ADRs in `docs/adr/`. Read the relevant ADR before changing hosting, storage, static files, HTTPS handling or auth. If you change one of those decisions, add a new ADR that supersedes it (template in `docs/adr/README.md`) rather than editing the old one, and keep the other docs current.

## Deployment

Production is a Docker container on the user's home server, managed by the separate `home-server` repo (sibling directory `../home-server`; read it for context but **don't edit it**). `docs/deployment.md` is the source of truth, including the edits home-server needs. Key facts:
- Pushing to `main` runs `.github/workflows/build.yml`: tests, then home-server's reusable `build-site-image.yml` pushes `ghcr.io/ssschoubye/ella:sha-<short>`. The server pins that tag; there is no `latest`.
- Traffic: Cloudflare (TLS) → cloudflared → Caddy → gunicorn on port 80. `config.settings.prod` trusts `X-Forwarded-Proto` and deliberately doesn't redirect to HTTPS (Cloudflare does it).
- All state lives in `DJANGO_DATA_DIR` (`/data`, bind-mounted from `/srv/state/ella`): SQLite DB, `media/`, and `backups/db.sqlite3`, written by `manage.py snapshot_db` from restic's pre-backup hook. The root filesystem is read-only; static files are collected at build time and served by WhiteNoise (enabled in prod settings only).
- `deploy/entrypoint.sh` chowns `/data` as root, drops to user `app` (uid 10001), runs `migrate`, then starts gunicorn. Migrations therefore run on every deploy.
- `/healthz/` is the container healthcheck and is exempt from the login wall. There is no Cloudflare Access in front of the site (ADR 0010); if one exists in the dashboard it must be deleted, or every request 302s to `cloudflareaccess.com`.
- Sign-on: **an invitation link where the person picks any email and a password** (ADR 0014). That is the whole of it — no identity provider, no SMTP, no list of allowed addresses, and `DJANGO_SECRET_KEY` is the only secret. django-axes locks out after 5 failures and is the main defence, since the login page is public. See `docs/security.md`.
- `/` is public (ADR 0012); everything else needs a session. Records are linked to the signed-in account (ADR 0011).

## Architecture

- **Settings:** `config/settings/base.py` is shared; `dev.py` / `prod.py` override DB, DEBUG, hosts, static storage and HTTPS hardening.
- **Login wall:** `core.middleware.LoginRequiredMiddleware` forces authentication on every path except the `EXEMPT_PREFIXES` (`/admin/`, `/static/`, `/healthz/`, `/accounts/`, `/invitation/`) and the `EXEMPT_PATHS` exact matches (`/`). The two lists are separate because `"/"` as a prefix would exempt the whole site. Views therefore don't use `@login_required` — new views are protected automatically.
- **Sign-on (`adgang`):** `Invitation` is a single-use, expiring, revocable link. **The signup form is on the invitation page itself** (`adgang/views.py`), so there is no separate signup URL that could be left open -- holding the token *is* the authorisation. The view re-checks the token on POST as well as GET, so a link revoked while the form sat open does not work; there is a test for that. Mint links in `/admin/` or with `manage.py invite "<name>"`.
- **Ops commands:** `manage.py invite "<name>"` mints a link, `list_people`
  shows every account and warns about any whose username is not an email (it
  can then only sign in at `/admin/`), `rename_login <old> <email>` moves an
  account's login. Prefer adding a command to pasting a `shell -c` one-liner
  into a doc.
- **The email address is the username**, lower-cased in both `SignupForm.clean_email` and `EmailLoginForm.clean_username` so `Anton@` and `anton@` cannot become two accounts. It is **never verified** -- the invitation link is the proof, and that is what removes any need for SMTP. The site sends no email at all.
- **`login()` must be passed `backend=`** when signing someone in after signup: `AxesStandaloneBackend` is also installed and Django refuses to guess between two backends.
- **django-axes answers 429**, not 403, and the lockout deliberately survives a subsequently-correct password -- otherwise the limit only delays a guesser until they land it.
- **"Who" fields are accounts:** `Booking.booker`, `ArchiveFile.uploaded_by`, `Ticket.created_by` and `Comment.author` are `ForeignKey`s to the user model with `SET_NULL`, set by the view from `request.user` and **absent from the forms** — don't add them back, there are tests pinning that. Render one with the `person` filter (`core/templatetags/people.py`), which falls back to the email local part and to "Ukendt".
- **Apps** (mounted in `config/urls.py`):
  - `core` — the front page (public landing for anonymous visitors, start page when signed in) plus placeholder pages (`logbog`, `skader`) rendered via `core/placeholder.html` for not-yet-built features, the login-wall middleware, and the `person` template filter.
  - `adgang` (`/invitation/<token>/`) — invitation links, the signup form that lives on them, and the login form. See the sign-on notes above.
  - `booking` (`/kalender/`) — boat calendar with month/week/list views. Recurring bookings are materialized as separate `Booking` rows sharing a `series_id` UUID (created via `bulk_create` in `add_booking`; `_shift_datetime`/`_add_months` compute occurrences). `delete_series` removes all rows with that `series_id`. `templatetags/booking_extras.py` provides the `danish_datetime` filter.
  - `filarkiv` (`/filarkiv/`) — file archive. Uploads go to `MEDIA_ROOT/filarkiv/<uuid>/<filename>`. There is intentionally **no `MEDIA_URL`** and nothing serves media directly: files are only reachable through the `download_file` view so they stay behind the login wall. Deleting a record must also delete the file (`file.delete(save=False)`).
  - `vedligehold` (`/vedligehold/`) — kanban-style maintenance ticket board with comments. Status changes go through `Ticket.set_status()` (manages `completed_at`). Tickets in "Færdige" are auto-archived (never deleted) after 30 days by `sweep_finished_tickets()`, which runs lazily on each board view — there's no cron/background job. The only way a ticket is deleted is a person pressing "Slet" (`ticket_delete`, POST only), which also removes its comments. Archived tickets can't be edited (`ticket_edit` redirects), since a status set there would leave them archived and off the board.
- **Frontend:** server-rendered Django templates extending `templates/base.html` (`title`, `extra_head`, `content`, `extra_js` blocks). Plain CSS in `static/css/style.css`, vanilla JS in `static/js/` (`event-modal.js` reads booking data from `data-*` attributes on calendar triggers). Date pickers use vendored flatpickr (`static/vendor/flatpickr`, Danish locale) bound to `.js-datetime-picker` inputs; forms use the `%Y-%m-%dT%H:%M` format. No JS build step.
- **Time:** `USE_TZ=True`, `TIME_ZONE=Europe/Copenhagen`; booking fields are `DateTimeField`s, so convert with `timezone.localtime` when displaying.
