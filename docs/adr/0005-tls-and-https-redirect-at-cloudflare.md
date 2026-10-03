# 0005. TLS and HTTPS redirects at Cloudflare

- **Status:** Accepted
- **Date:** 2026-10-03

## Context
Traffic arrives as browser → Cloudflare (TLS) → cloudflared → Caddy →
gunicorn. Inside the server everything is plain HTTP. Caddy runs with
`auto_https off` and trusts private-range proxies, so it passes on
cloudflared's `X-Forwarded-Proto: https`. The container healthcheck calls
`http://127.0.0.1/healthz/` from inside the container, with no forwarded
header.

## Decision
In `config.settings.prod`:
- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`, so Django
  knows requests were HTTPS (secure cookies, CSRF origin checks).
- `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` on.
- `SECURE_SSL_REDIRECT` **off** by default (`DJANGO_SECURE_SSL_REDIRECT` turns
  it on). Cloudflare's "Always Use HTTPS" does the redirect.
- HSTS is left to Cloudflare. The `check --deploy` warnings W004 and W008 are
  silenced with a comment saying why.
- `ALLOWED_HOSTS` defaults to `ella.molder.app` plus `localhost`/`127.0.0.1`
  for the healthcheck.

## Consequences
- The healthcheck works without special cases in Django.
- Trusting `X-Forwarded-Proto` is safe only because nothing reaches the
  container except through Caddy on the internal `edge` network. If the
  container is ever published on a host port, revisit this.
- "Always Use HTTPS" and HSTS must stay enabled for `molder.app` in Cloudflare.
  That setting now enforces HTTPS for the site.

## Alternatives considered
- **`SECURE_SSL_REDIRECT=True` plus exempting `/healthz/`:** works, but
  duplicates what the edge already guarantees and adds a config path that's
  only exercised in production.
