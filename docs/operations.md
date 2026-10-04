# Operations

Day-to-day tasks for whoever looks after the site. Server commands run on the
home server; `make` targets run from a home-server checkout on the desktop.
Deploying, updating and restoring are in [deployment.md](deployment.md).

## Adding a person

Send them an invitation link. That is the whole procedure — there is no list to
edit, no account to create, no password to invent, and nothing to deploy
([ADR 0010](adr/0010-invitation-links-and-google-sign-in.md)).

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

They open the link, press "Fortsæt med Google", and they are in. Their name
appears in the app from their Google profile, so there is nothing to type in
anywhere.

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

## Resetting the admin password

Nobody in the group has a password, so there is nothing to reset for them — if
they lose access to their Google account, that is Google's recovery flow, not
ours.

The one password is the superuser's, for `/admin/`:

```bash
docker exec -it -u app ella python manage.py changepassword <username>
```

The first admin account is created with `createsuperuser`
([deployment.md](deployment.md#first-deploy)). Use your own Google address for
it: signing in with Google then attaches to the same account rather than
creating a second one.

Five wrong attempts locks that IP out of `/admin/` for 30 minutes
(django-axes). To clear a lockout you imposed on yourself:

```bash
docker exec -it -u app ella python manage.py axes_reset
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

## Running management commands

The container runs as `app`. Use `-u app`, otherwise files created by the
command are owned by root:

```bash
docker exec -it -u app ella python manage.py <command>
```
