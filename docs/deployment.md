# Deploying ella to the home server

Ella runs as a container on the home server, managed by the
[`home-server`](https://github.com/ssschoubye/home-server) repo:

```
browser ──https──▶ Cloudflare ──tunnel──▶ cloudflared ──http──▶ Caddy ──http──▶ ella:80 (gunicorn)
                                                                                   │
                                                              /srv/state/ella ◀────┘ /data
```

- **This repo** builds the image (`Dockerfile`) and pushes it to
  `ghcr.io/ssschoubye/ella:sha-<short>` via `.github/workflows/build.yml`.
- **home-server** pins the tag, owns the route (Caddyfile), the public hostname
  (cloudflared), secrets (sops), backups (restic) and monitoring.

## What the image does

| | |
|---|---|
| Port | HTTP on **80**, gunicorn with 2 workers (`GUNICORN_WORKERS` to change) |
| Settings | `config.settings.prod` (baked in as `DJANGO_SETTINGS_MODULE`) |
| State | Everything under **`/data`**: `db.sqlite3` (+ `-wal`/`-shm`), `media/` (filarkiv uploads), `backups/db.sqlite3` (snapshot) |
| Static files | Collected at build time, served by WhiteNoise. No Nginx, no static volume |
| Startup | `deploy/entrypoint.sh`: as root, creates `/data/{media,backups}` and `chown -R`s `/data` to the `app` user (uid 10001); drops to `app`; runs `migrate`; starts gunicorn |
| Health | `GET /healthz/` → `200 ok` (bypasses the login wall, touches the DB) |
| Root FS | Works with `read_only: true` + tmpfs `/tmp` |
| HTTPS | Cloudflare terminates TLS and redirects to HTTPS. Django trusts `X-Forwarded-Proto` (from cloudflared, passed through by Caddy) and keeps secure cookies on. It does not redirect by itself |

Environment variables (defaults are right for `ella.molder.app`):

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | **Required.** Comes from sops |
| `GOOGLE_OAUTH_CLIENT_ID` | — | **Required**, or nobody can sign in. From sops; see [security.md](security.md#google-oauth-client) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | — | **Required.** Same place |
| `DJANGO_PUBLIC_BASE_URL` | `https://ella.molder.app` | What invitation links are built from. A management command has no request to derive a host from |
| `DJANGO_INVITATION_VALID_DAYS` | `30` | How long a new invitation link stays usable |
| `DJANGO_ALLOWED_HOSTS` | `ella.molder.app,localhost,127.0.0.1` | localhost is needed for the healthcheck |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://ella.molder.app` | |
| `DJANGO_DATA_DIR` | `/data` | |
| `DJANGO_TIME_ZONE` | `Europe/Copenhagen` | |

---

## Changes needed in home-server

The current `stacks/sites/ella` was made from the static-site template and
assumes ella is stateless. It isn't: it has a database, uploads and a secret.
These are the edits, in one commit.

### 1. `stacks/sites/ella/compose.yml`

```yaml
services:
  ella:
    image: ghcr.io/${GITHUB_USER:?set in .env}/${SITE_NAME:-ella}:${SITE_IMAGE_TAG:?pin a tag, never latest}
    container_name: ${SITE_NAME:-ella}
    restart: unless-stopped
    networks:
      - edge
    env_file:
      - ${CONFIG_ROOT:?set in .env}/ella.env      # Django key + Google OAuth, from secrets/ella.sops.yaml
    volumes:
      - ${STATE_ROOT:?set in .env}/ella:/data     # SQLite DB, uploads, backup snapshot
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
    healthcheck:
      # python:slim has no wget/curl.
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1/healthz/', timeout=4)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

networks:
  edge:
    external: true
    name: ${EDGE_NETWORK:-edge}
```

The differences from today are `env_file`, `volumes` and the healthcheck. The
`/var/run` tmpfs is no longer needed. Leave out `user:`: the entrypoint must
start as root to fix the ownership of `/data`, because the stacks role resets
`/srv/state/ella` to `root:root 0755` on every deploy. It then drops
privileges, which `no-new-privileges` allows.

### 2. `ansible/group_vars/all.yml`

```yaml
  - name: ella
    path: stacks/sites/ella
    state_dirs: [ella]
    requires_files:
      - "{{ config_root }}/ella.env"
    env:
      GITHUB_USER: "{{ github_user }}"
      SITE_NAME: ella
      SITE_IMAGE_TAG: "{{ ella_site_image_tag }}"
      EDGE_NETWORK: "{{ docker_network_edge }}"
      STATE_ROOT: "{{ state_root }}"
      CONFIG_ROOT: "{{ config_root }}"
```

Add the secret to `sops_secret_files`:

```yaml
  - name: ella
    src: secrets/ella.sops.yaml
    dest: "{{ config_root }}/ella.env"
```

Back up the snapshot, not the live database, by adding this to
`restic_exclude_patterns`:

```yaml
  - "{{ state_root }}/ella/db.sqlite3*"     # live DB + WAL; backups/db.sqlite3 is the consistent copy
```

### 3. `secrets/ella.sops.yaml.example` → `secrets/ella.sops.yaml`

```yaml
# Template only. Fill in, encrypt with sops, commit the ENCRYPTED file.
#   sops --encrypt this-file > secrets/ella.sops.yaml
#
# Decrypted to /etc/home-server/ella.env and read by the ella stack.
# Generate the key with:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

DJANGO_SECRET_KEY: CHANGE_ME_ELLA_DJANGO_SECRET_KEY
GOOGLE_OAUTH_CLIENT_ID: CHANGE_ME_GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET: CHANGE_ME_GOOGLE_OAUTH_CLIENT_SECRET
```

Rotating the Django key logs everyone out and nothing else. The Google
credentials come from [security.md](security.md#google-oauth-client); without
them the site runs but nobody can sign in.

### 4. Backup pre-hook

`restic-backup` runs every executable in `/etc/home-server/backup-pre.d/`
before snapshotting, and **refuses to back up anything** if one fails. So
the hook skips cleanly when the container isn't running. In that case the
previous `backups/db.sqlite3` is still on disk and gets backed up as-is.

`/etc/home-server/backup-pre.d/10-ella-sqlite` (mode `0755`, e.g. installed
by a `copy` task in the backups role):

```sh
#!/bin/sh
# Consistent copy of ella's SQLite DB -> /srv/state/ella/backups/db.sqlite3
set -eu
if [ "$(docker inspect -f '{{.State.Running}}' ella 2>/dev/null)" != "true" ]; then
    echo "ella is not running; keeping the previous snapshot"
    exit 0
fi
exec docker exec -u app ella python manage.py snapshot_db
```

### 5. Docs

`stacks/sites/ella/README.md` and the comment in `compose.yml` both say the
site is stateless and absent from `restic_paths`. That's no longer true:
`/srv/state` is already in `restic_paths`, so `/srv/state/ella` is backed up
without adding anything there. Only the exclude above and the hook are new.

`monitoring/blackbox`: change the probe target to
`https://ella.molder.app/healthz/`. The front page would also answer 200 now
that it is public ([ADR 0012](adr/0012-public-front-page.md)), but `/healthz/`
touches the database, so it proves rather more. There is no Access Bypass
policy to arrange, because there is no Access ([ADR 0010](adr/0010-invitation-links-and-google-sign-in.md)).

---

## One-time GitHub setup

1. **Reusable workflow access.** home-server is private, so ella's workflow
   can only call `build-site-image.yml` if you allow it: home-server →
   Settings → Actions → General → *Access* → "Accessible from repositories
   owned by the user 'ssschoubye'".
2. **Package visibility.** After the first build, the `ella` package on GHCR
   is private. Either make it public (Package settings → Change visibility) or
   give Docker on the server a pull credential. The image contains only code
   and no data or secrets, so public is fine.

## First deploy

1. Push to `main` here and wait for the `build` workflow. Copy
   `SITE_IMAGE_TAG=sha-…` from the run summary.
2. In home-server, set `ella_site_image_tag`, make the changes above, commit,
   `make deploy SERVICE=ella`.
3. Create the break-glass admin. Use **your own Google address**: signing in
   with Google later attaches to this same account instead of making a
   second one.
   ```bash
   docker exec -it -u app ella python manage.py createsuperuser
   ```
4. Invite yourself, and check the whole flow end to end before sending
   anyone else a link:
   ```bash
   docker exec -it -u app ella python manage.py invite "Dig selv"
   ```
   Open the printed link in a private window and press "Fortsæt med
   Google". If Google shows `redirect_uri_mismatch`, the redirect URI on
   the OAuth client is wrong — see
   [security.md](security.md#google-oauth-client).
5. Invite the rest of the group from `/admin/`
   ([operations.md](operations.md#adding-a-person)).
6. `curl -I https://ella.molder.app/healthz/` should return `200`, and
   `curl -I https://ella.molder.app/` should return `200` rather than a 302.

**Bringing over local data instead** (optional, before step 2's first start,
or with the container stopped):

```bash
scp db.sqlite3 server:/tmp/ && scp -r media server:/tmp/
sudo install -d /srv/state/ella
sudo mv /tmp/db.sqlite3 /srv/state/ella/ && sudo mv /tmp/media /srv/state/ella/
# ownership is fixed by the entrypoint on the next start
```

## Updating

Push to `main` → copy the new tag → bump `ella_site_image_tag` → commit →
`make deploy SERVICE=ella`. Migrations run automatically on start. To roll
back, deploy the previous tag. That's only safe if no migration in between
changed the schema; otherwise restore the DB too.

## Restoring the database

```bash
docker stop ella
# restore /srv/state/ella/backups/db.sqlite3 from restic, then:
sudo cp /srv/state/ella/backups/db.sqlite3 /srv/state/ella/db.sqlite3
sudo rm -f /srv/state/ella/db.sqlite3-wal /srv/state/ella/db.sqlite3-shm
docker start ella
```

`media/` is backed up directly and restores as-is.

## Testing the image locally

```bash
docker build -t ella:test .
docker run --rm -p 8080:80 --read-only --tmpfs /tmp \
  --security-opt no-new-privileges -v "$PWD/.data:/data" \
  -e DJANGO_SECRET_KEY=local-test-key-local-test-key-local-test-key-123 \
  ella:test
curl -i localhost:8080/healthz/
```

- In Git Bash on Windows, prefix with `MSYS_NO_PATHCONV=1`, or `/data` and `/tmp`
  get rewritten into Windows paths.
- Logging in through a browser at `http://localhost:8080` won't work: session
  and CSRF cookies are `Secure`, so they're only sent over HTTPS, as in
  production. Use `docker exec -it -u app <container> python manage.py shell` to poke at
  data, or send `X-Forwarded-Proto: https` and pass cookies by hand with curl.

## Access control

Sign-on is Google, with sign-up gated on a single-use invitation link, and no
Cloudflare Access ([ADR 0010](adr/0010-invitation-links-and-google-sign-in.md)).
The one-time Google OAuth client setup is in
[security.md](security.md#google-oauth-client); inviting and removing people is
in [operations.md](operations.md#adding-a-person).

If an old Cloudflare Access application still covers `ella.molder.app`,
**delete it**. While it exists every request is intercepted and the site
answers `302` to `<team>.cloudflareaccess.com`, which looks exactly like a
tunnel fault.
