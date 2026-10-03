# 0009. Self-hosted identity provider: deferred, and not Keycloak

- **Status:** Deferred
- **Date:** 2026-10-03

## Context
A self-hosted OpenID Connect identity provider would give one account across
every app on the home server, with 2FA or passkeys, lockout and password reset
handled centrally. Ella is currently the only app that needs logins.

## Decision
Don't run an identity provider yet. When two or three self-hosted apps need
shared logins, add a **lightweight** one as its own home-server stack:
- **Authelia:** tens of MB of RAM, SQLite-capable. It can protect apps directly
  through Caddy `forward_auth`, and it's also an OIDC provider.
- **Pocket ID:** passkey-only OIDC, very small, with no passwords to guess.

Choose **Keycloak** only to learn it or to get features those lack. It needs
a JVM (0.5–1 GB RAM), Postgres, SMTP and frequent upgrades, which is heavy for
the current laptop server.

## Consequences
- When an identity provider is introduced:
  - Ella connects via `mozilla-django-oidc` (or `django-allauth`), matching
    accounts by email.
  - Cloudflare Access ([0007](0007-cloudflare-access-in-front-of-the-site.md))
    can use the same provider as its login method, so nothing done now is
    thrown away.
  - That's also the natural moment to link records to accounts
    ([0008](0008-records-are-not-linked-to-user-accounts.md)).
- The provider becomes the most critical service on the server (if it's down,
  nobody can log in to anything). It needs its own backup, monitoring and a
  break-glass admin login in each app.
- `1Projects/SSO` (the Olivo identity provider) is a separate product deployed
  from its own infrastructure, and is deliberately not used for personal
  projects.
