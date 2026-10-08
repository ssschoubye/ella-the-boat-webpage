# Architecture Decision Records

Short records of decisions that shape this project: what was decided, why, and
what it costs. They're written when a decision is made and are not rewritten
afterwards. If a decision changes, add a new ADR that supersedes the old one and
set the old one's status to `Superseded by ADR-NNNN`.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-run-as-a-container-on-the-home-server.md) | Run as a container on the home server | Accepted |
| [0003](0003-sqlite-on-a-bind-mount-with-snapshot-backups.md) | SQLite on a bind mount, with snapshot backups | Accepted |
| [0004](0004-serve-static-files-with-whitenoise.md) | Serve static files with WhiteNoise from the image | Accepted |
| [0005](0005-tls-and-https-redirect-at-cloudflare.md) | TLS and HTTPS redirects at Cloudflare | Accepted |
| [0006](0006-site-wide-login-wall-and-private-uploads.md) | Site-wide login wall and private uploads | Accepted |
| [0007](0007-cloudflare-access-in-front-of-the-site.md) | Cloudflare Access in front of the site | Superseded by 0010 |
| [0008](0008-records-are-not-linked-to-user-accounts.md) | Records are not linked to user accounts (for now) | Superseded by 0011 |
| [0009](0009-self-hosted-identity-provider-deferred.md) | Self-hosted identity provider: deferred, and not Keycloak | Deferred |
| [0010](0010-invitation-links-and-google-sign-in.md) | Invitation links and Google sign-in, instead of Cloudflare Access | Superseded by 0014 |
| [0011](0011-records-linked-to-accounts.md) | Records are linked to accounts | Accepted |
| [0012](0012-public-front-page.md) | A public front page | Accepted |
| [0013](0013-email-sign-in-codes.md) | Email sign-in codes alongside Google, sent through Resend | Superseded by 0014 |
| [0014](0014-invite-links-and-passwords.md) | Invitation links and a password, and nothing else | Accepted |
| [0015](0015-filarkiv-folders-and-inline-images.md) | Filarkiv folders, and pictures shown in the browser | Accepted |

## Writing a new one

Copy the template below to `NNNN-short-title.md` with the next number, and add
it to the table.

```markdown
# NNNN. Title

- **Status:** Proposed | Accepted | Deferred | Superseded by ADR-NNNN
- **Date:** YYYY-MM-DD

## Context
What forces are at play, and why a decision is needed now.

## Decision
What we're doing, stated plainly.

## Consequences
What gets easier, what gets harder, and what we now have to look after.

## Alternatives considered
What else was on the table and why it lost.
```
