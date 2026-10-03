# 0007. Cloudflare Access in front of the site

- **Status:** Accepted
- **Date:** 2026-10-03

## Context
Once the site is public, its only protection is Django's username/password
login ([0006](0006-site-wide-login-wall-and-private-uploads.md)). It has:
- no rate limit or lockout on `/login/` or `/admin/login/`, both of which are
  public;
- no second factor;
- no self-service password reset.

The group is about six people. The site already sits behind a Cloudflare Tunnel
([0002](0002-run-as-a-container-on-the-home-server.md)). The server is a
16 GB laptop that also runs monitoring and backups.

## Decision
Put **Cloudflare Access** (Zero Trust, free plan) in front of
`ella.molder.app`:
- One self-hosted Access application for the whole hostname. Its Allow policy
  lists the group's email addresses, and login is by email one-time PIN.
- A second, path-specific application for `ella.molder.app/healthz` with a
  **Bypass** policy, so the blackbox probe and Cloudflare health checks keep
  working.
- The Django login stays as a second layer. People log in twice (Cloudflare
  first, then Django), which is accepted for now.

Setup steps are in [security.md](../security.md#cloudflare-access-setup).

## Consequences
- Password guessing never reaches the server: anonymous requests stop at
  Cloudflare. `/admin/` is covered too.
- Effectively two factors: something you have (your inbox) plus the Django
  password.
- No code, no new service on the server, and nothing extra to back up.
- Adding a person means adding their email to the Access policy *and*
  creating a Django account ([operations.md](../operations.md#adding-a-person)).
- More dependence on Cloudflare. The tunnel already depends on it, so this
  adds no new single point of failure.
- Double login is the main annoyance. It can be removed later by having Django
  trust the signed `Cf-Access-Jwt-Assertion` header and map the email to a
  user. That needs signature verification against the team's public keys,
  never just trusting the header.

## Alternatives considered
- **Hardening the Django login** (rate limiting with `django-axes`, 2FA with
  `django-otp`): self-contained, but the login page stays public, it takes
  days of work, and every future app would repeat it. Rate limiting may still
  be added later as defence in depth.
- **Keycloak:** single sign-on for every future app and full-featured, but it
  needs a JVM (0.5–1 GB RAM) and Postgres, an SMTP setup, frequent upgrades,
  and it becomes a public login page and a single point of failure on a
  laptop. Far more system than six users need. See [0009](0009-self-hosted-identity-provider-deferred.md).
- **Authelia / Pocket ID:** lightweight self-hosted identity servers. They're
  the right tool once several self-hosted apps need shared logins, but not
  needed yet ([0009](0009-self-hosted-identity-provider-deferred.md)).
