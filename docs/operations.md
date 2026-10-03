# Operations

Day-to-day tasks for whoever looks after the site. Server commands run on the
home server; `make` targets run from a home-server checkout on the desktop.
Deploying, updating and restoring are in [deployment.md](deployment.md).

## Adding a person

A person needs up to three things:

1. **Cloudflare Access:** add their email to the `Bådfolk` policy (or the
   Access group). See [security.md](security.md#cloudflare-access-setup).
2. **A Django account:**
   - Log in at `https://ella.molder.app/admin/` as a staff user and go to
     *Users → Add user*.
   - Set a temporary password and send it to them by a different channel than
     the site link.
   - Leave *Staff status* off unless they should be able to use `/admin/`.
3. **A name in the dropdowns** (only if they should be selectable as booker,
   uploader or ticket author). The list is hardcoded
   ([ADR 0008](adr/0008-records-are-not-linked-to-user-accounts.md)):
   - Edit `BOOKER_CHOICES` in `booking/models.py`. Rename the placeholder
     `person_6` or add `person_7`, but **never reorder or reuse existing keys**,
     because stored records refer to them.
   - Run `python manage.py makemigrations`. Choice changes create small
     migrations in `booking`, `filarkiv` and `vedligehold`.
   - Commit, push, and deploy the new tag. Migrations run on container start.

## Removing a person

1. Remove their email from the Access policy, then revoke their sessions:
   *Zero Trust → Team & Resources → Users*, select them, then *Action → Revoke
   → Revoke sessions*. Revoking alone isn't enough: anyone still allowed by the
   policy can just request a new code.
2. In `/admin/`, untick **Active** on their account. Don't delete it.
3. Leave their entry in `BOOKER_CHOICES`, so old bookings and files still show
   their name.

## Resetting a password

From `/admin/` (*Users → user → "this form"* link under the password), or on
the server:

```bash
docker exec -it -u app ella python manage.py changepassword <username>
```

The first admin account is created the same way, with `createsuperuser`
([deployment.md](deployment.md#first-deploy)).

## Logs and health

```bash
make logs SERVICE=ella      # from home-server: container logs (gunicorn access + Django)
make status                 # container status, including health
docker inspect -f '{{.State.Health.Status}}' ella
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

## Running management commands

The container runs as `app`. Use `-u app`, otherwise files created by the
command are owned by root:

```bash
docker exec -it -u app ella python manage.py <command>
```
