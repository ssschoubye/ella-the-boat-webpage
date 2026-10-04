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

## Documentation

`docs/` holds architecture, deployment, security/sign-on and operations docs (index: `docs/README.md`). Decisions are recorded as ADRs in `docs/adr/`. Read the relevant ADR before changing hosting, storage, static files, HTTPS handling or auth. If you change one of those decisions, add a new ADR that supersedes it (template in `docs/adr/README.md`) rather than editing the old one, and keep the other docs current.

## Deployment

Production is a Docker container on the user's home server, managed by the separate `home-server` repo (sibling directory `../home-server`; read it for context but **don't edit it**). `docs/deployment.md` is the source of truth, including the edits home-server needs. Key facts:
- Pushing to `main` runs `.github/workflows/build.yml`: tests, then home-server's reusable `build-site-image.yml` pushes `ghcr.io/ssschoubye/ella:sha-<short>`. The server pins that tag; there is no `latest`.
- Traffic: Cloudflare (TLS) → cloudflared → Caddy → gunicorn on port 80. `config.settings.prod` trusts `X-Forwarded-Proto` and deliberately doesn't redirect to HTTPS (Cloudflare does it).
- All state lives in `DJANGO_DATA_DIR` (`/data`, bind-mounted from `/srv/state/ella`): SQLite DB, `media/`, and `backups/db.sqlite3`, written by `manage.py snapshot_db` from restic's pre-backup hook. The root filesystem is read-only; static files are collected at build time and served by WhiteNoise (enabled in prod settings only).
- `deploy/entrypoint.sh` chowns `/data` as root, drops to user `app` (uid 10001), runs `migrate`, then starts gunicorn. Migrations therefore run on every deploy.
- `/healthz/` is the container healthcheck and is exempt from the login wall. There is no Cloudflare Access in front of the site (ADR 0010); if one exists in the dashboard it must be deleted, or every request 302s to `cloudflareaccess.com`.
- Sign-on: **Google or a one-time code emailed to any address, both gated on a single-use invitation link** (ADR 0010, ADR 0013). No passwords except the `/admin/` superuser, which django-axes locks out after 5 failures. `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET` and the Resend SMTP settings come from sops; without them the site runs and serves its public front page, but that route cannot sign anyone in. See `docs/security.md`.
- `/` is public (ADR 0012); everything else needs a session. Records are linked to the signed-in account (ADR 0011).

## Architecture

- **Settings:** `config/settings/base.py` is shared; `dev.py` / `prod.py` override DB, DEBUG, hosts, static storage and HTTPS hardening.
- **Login wall:** `core.middleware.LoginRequiredMiddleware` forces authentication on every path except the `EXEMPT_PREFIXES` (`/admin/`, `/static/`, `/healthz/`, `/accounts/`, `/invitation/`) and the `EXEMPT_PATHS` exact matches (`/`). The two lists are separate because `"/"` as a prefix would exempt the whole site. Views therefore don't use `@login_required` — new views are protected automatically.
- **Sign-on (`adgang`):** `Invitation` is a single-use, expiring, revocable link. `views.invitation` parks the token in the session, and **both** adapters -- `InvitationOnlyAccountAdapter` (email codes) and `InvitationOnlySocialAccountAdapter` (Google) -- allow a signup only while a usable one is held. Changing one without the other opens a hole; a test asserts they refuse together. The link is spent by the `user_signed_up` receiver in `signals.py`, which is the one place that fires on both paths. `pre_social_login` attaches Google to an existing account with the same **verified** email, which is what lets the `createsuperuser` admin use the owner's own Google address. Mint links in `/admin/` or with `manage.py invite "<name>"`.
- **No passwords, deliberately, but `SOCIALACCOUNT_ONLY` is OFF** -- it would disable the local-account machinery the email-code route needs. What keeps passwords out is `ACCOUNT_SIGNUP_FIELDS = ["email*"]`, which omits them, so accounts get an unusable password hash. Don't "fix" this by re-enabling `SOCIALACCOUNT_ONLY`.
- **Sending mail** is only ever sign-in and verification codes. `base.py` defaults to the console backend so local dev needs no SMTP (the code appears in the `runserver` output); `prod.py` defaults to SMTP, pointed at Resend. allauth's own rate limits do the throttling -- django-axes never sees code entry, because it does not call `authenticate()`.
- **"Who" fields are accounts:** `Booking.booker`, `ArchiveFile.uploaded_by`, `Ticket.created_by` and `Comment.author` are `ForeignKey`s to the user model with `SET_NULL`, set by the view from `request.user` and **absent from the forms** — don't add them back, there are tests pinning that. Render one with the `person` filter (`core/templatetags/people.py`), which falls back to the email local part and to "Ukendt".
- **Apps** (mounted in `config/urls.py`):
  - `core` — the front page (public landing for anonymous visitors, start page when signed in) plus placeholder pages (`logbog`, `skader`) rendered via `core/placeholder.html` for not-yet-built features, the login-wall middleware, and the `person` template filter.
  - `adgang` (`/invitation/<token>/`) — invitation links and the allauth adapters. See the sign-on note above.
  - `booking` (`/kalender/`) — boat calendar with month/week/list views. Recurring bookings are materialized as separate `Booking` rows sharing a `series_id` UUID (created via `bulk_create` in `add_booking`; `_shift_datetime`/`_add_months` compute occurrences). `delete_series` removes all rows with that `series_id`. `templatetags/booking_extras.py` provides the `danish_datetime` filter.
  - `filarkiv` (`/filarkiv/`) — file archive. Uploads go to `MEDIA_ROOT/filarkiv/<uuid>/<filename>`. There is intentionally **no `MEDIA_URL`** and nothing serves media directly: files are only reachable through the `download_file` view so they stay behind the login wall. Deleting a record must also delete the file (`file.delete(save=False)`).
  - `vedligehold` (`/vedligehold/`) — kanban-style maintenance ticket board with comments. Status changes go through `Ticket.set_status()` (manages `completed_at`). Tickets in "Færdige" are auto-archived (never deleted) after 30 days by `sweep_finished_tickets()`, which runs lazily on each board view — there's no cron/background job.
- **Frontend:** server-rendered Django templates extending `templates/base.html` (`title`, `extra_head`, `content`, `extra_js` blocks). Plain CSS in `static/css/style.css`, vanilla JS in `static/js/` (`event-modal.js` reads booking data from `data-*` attributes on calendar triggers). Date pickers use vendored flatpickr (`static/vendor/flatpickr`, Danish locale) bound to `.js-datetime-picker` inputs; forms use the `%Y-%m-%dT%H:%M` format. No JS build step.
- **Time:** `USE_TZ=True`, `TIME_ZONE=Europe/Copenhagen`; booking fields are `DateTimeField`s, so convert with `timezone.localtime` when displaying.
