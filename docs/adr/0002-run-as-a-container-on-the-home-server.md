# 0002. Run as a container on the home server

- **Status:** Accepted
- **Date:** 2026-10-03

## Context
The original plan (from the starter template) was a Hetzner Cloud VPS running
Postgres, Gunicorn under systemd and Nginx with Certbot. Meanwhile the owner
built a home server managed as code in the `home-server` repo. It already has
a pattern for sites: an image is built in the site's repo by a reusable GitHub
Actions workflow and pushed to GHCR. The server pins an immutable tag. Caddy
routes to the container on a shared `edge` network, and a Cloudflare Tunnel
exposes it publicly with no inbound ports. A stack for `ella` at
`ella.molder.app` was already sketched there, assuming a static site.

## Decision
Ship ella as a Docker image (`ghcr.io/ssschoubye/ella:sha-<short>`) that fits
the home-server site contract:
- HTTP on port 80, run by gunicorn.
- A read-only root filesystem with a tmpfs at `/tmp`.
- `no-new-privileges`.
- A `/healthz/` endpoint for the container healthcheck.

The image is built by `.github/workflows/build.yml`, which runs the tests and
then calls home-server's `build-site-image.yml`. Deploying means pinning the
printed tag in home-server and running `make deploy SERVICE=ella`. The
entrypoint runs migrations on every start.

Drop the Hetzner artefacts (`deploy/nginx.conf`, `deploy/gunicorn.service`,
and the Postgres settings).

## Consequences
- No VPS cost, and the site gets the home server's monitoring, backups and
  secrets handling for free.
- home-server owns routing, secrets and backups, so some changes span two
  repos. [deployment.md](../deployment.md) lists exactly what home-server
  needs.
- The site depends on the home server's uptime, on Wi-Fi. That's acceptable
  for a booking calendar among friends.
- Rolling back means deploying the previous tag. That's only safe if no
  migration in between changed the schema.
- Running migrations on startup is fine with one container. It would need
  revisiting if there were ever several replicas.

## Alternatives considered
- **Hetzner VPS as planned:** more independent, but a second server to patch
  and pay for, and it duplicates what home-server already provides.
- **systemd + virtualenv directly on the home server:** breaks home-server's
  rule that everything runs as a pinned container, and makes rollback and
  migration to new hardware harder.
