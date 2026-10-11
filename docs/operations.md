# Operations

Day-to-day tasks for whoever looks after the site. Server commands run on the
home server; `make` targets run from a home-server checkout on the desktop.
Deploying, updating and restoring are in [deployment.md](deployment.md).

## Adding a person

Send them an invitation link. That is the whole procedure — there is no list to
edit, no account to create for them, and nothing to deploy
([ADR 0014](adr/0014-invite-links-and-passwords.md)).

**From the admin**, which works from a phone:

1. `https://ella.molder.app/admin/adgang/invitation/add/`
2. Fill in **Til** with who it is for. It is only for your own overview; the
   person never sees it.
3. Save. The change page now shows **Link til afsendelse**. Copy it and send it
   however you normally reach them.

**Or from the server**, which is how you make the very first one:

```bash
docker exec -it -u app ella python manage.py invite "Anton"
# https://ella.molder.app/invitation/8Kd3...  <- send this
# Gyldigt til 03-11-2026 14:22. Kan bruges én gang.
```

`--days 7` for a shorter life.

They open the link and fill in three things: their first name, any email
address they like, and a password. The account exists from that moment and
they are signed in. Nothing is emailed to them, so there is nothing to wait
for and no spam folder to check.

The name is what the others see on their bookings and comments. The email is
what they log in with.

A few things worth knowing:

- **Treat the link like a door code.** Anyone holding it can create an
  account. Send it directly to the person, not to a group chat you do not
  control.
- Each link works **once** and expires after 30 days. If someone sits on it too
  long, make another; they are free.
- Changed your mind before they used it? Open it in the admin and tick
  **Tilbagekaldt**. It stops working at once.
- The admin list shows every invitation with a status: `Klar`, `Brugt`,
  `Udløbet` or `Tilbagekaldt`, and who used it.

## Removing a person

In `/admin/` → *Users* → their account, untick **Active**. Do not delete it:
their name should stay on the bookings and files they made, and deleting the
account sets those fields to NULL, which renders as "Ukendt"
([ADR 0011](adr/0011-records-linked-to-accounts.md)).

Being inactive stops them at the next request. To end a session already in
flight, rotate `DJANGO_SECRET_KEY` ([security.md](security.md#secrets)), which
logs everyone out.

There is no Access policy to edit any more, and nothing to deploy.

## Resetting a forgotten password

The site sends no email, so there is no self-service reset — this is the one
recurring manual job the design trades for having no SMTP, no identity
provider and no secrets to rotate
([ADR 0014](adr/0014-invite-links-and-passwords.md)).

Easiest, from a phone: `/admin/` → *Users* → their account → the **"this
form"** link under the password field, set a new one, and tell them through
some channel other than the site.

Or on the server:

```bash
docker exec -it -u app ella python manage.py changepassword <their-email>
```

The username *is* their email address.

Do not send a fresh invitation link instead: links only create new accounts,
so that would give them a second account and detach them from their own
bookings and uploads.

### Lockouts

Five wrong attempts locks that IP, and that (email, IP) pair, out for 30
minutes. A locked-out person gets a `429` page telling them to wait. To clear
it immediately:

```bash
docker exec -it -u app ella python manage.py axes_reset
```

The first admin account is created with `createsuperuser`
([deployment.md](deployment.md#first-deploy)). Answer its `Username:` prompt
with an **email address**: the username is the login identifier everywhere
else, and `/login/` is an email field, so a superuser named `soren` can only
get in via `/admin/`.

To check what you ended up with:

```bash
docker exec -u app ella python manage.py list_people
```

If the superuser's username is not an email address, rename it. Nothing
references the username, so this is safe:

```bash
docker exec -u app ella python manage.py rename_login soren soren@example.com
```

## Logs and health

```bash
make logs SERVICE=ella      # from home-server: container logs (gunicorn access + Django)
make status                 # container status, including health
docker inspect -f '{{.State.Health.Status}}' ella
```

Logins and invitation acceptances are logged, so the journal shows who got in
and when:

```bash
make logs SERVICE=ella | grep -E "Successful login|Invitation .* accepted"
```

Logs also go to VictoriaLogs through the home server's Vector pipeline. The
blackbox probe on `https://ella.molder.app/healthz/` raises the `SiteDown`
alert if the site, Caddy or the tunnel stops answering.

## Backups

Nightly and automatic ([ADR 0003](adr/0003-sqlite-on-a-bind-mount-with-snapshot-backups.md)).
To take one now, run `make backup-now` from home-server. To check the snapshot
is fresh:

```bash
ls -l /srv/state/ella/backups/db.sqlite3
```

Accounts and invitations are rows in that database, so they are covered by the
same backup as the bookings.

## Picture thumbnails

Thumbnails for the filarkiv grid are made when a picture is uploaded. After
deploying the folder version for the first time, or if a thumbnail is
missing, make the missing ones:

```bash
docker exec -u app ella python manage.py make_thumbnails
```

It skips pictures that already have one, so it is safe to run again.

## Running management commands

The container runs as `app`. Use `-u app`, otherwise files created by the
command are owned by root:

```bash
docker exec -it -u app ella python manage.py <command>
```
