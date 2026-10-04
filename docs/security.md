# Security and sign-on

## Layers

| Layer | What it does | Owned by |
|---|---|---|
| Cloudflare Tunnel | No inbound ports on the router or server, and the home IP is never published; only Cloudflare can reach Caddy | home-server |
| Cloudflare edge | TLS, "Always Use HTTPS", HSTS ([ADR 0005](adr/0005-tls-and-https-redirect-at-cloudflare.md)) | Cloudflare dashboard |
| **Invite-only sign-up** | An account can only be created while holding an unused invitation link ([ADR 0010](adr/0010-invitation-links-and-google-sign-in.md)) | this repo |
| **Google sign-in** | No passwords for the group; the credential is their Google account, with whatever 2FA they have on it | this repo + Google Cloud |
| Login wall | Every page requires a session except the public front page, the sign-on flow, `/admin/`, `/static/` and `/healthz/` ([ADR 0006](adr/0006-site-wide-login-wall-and-private-uploads.md), [ADR 0012](adr/0012-public-front-page.md)) | this repo |
| django-axes | Locks out an IP after 5 failed password attempts for 30 minutes. `/admin/` is the only password form left | this repo |
| Private uploads | No `MEDIA_URL`; files only via the signed-in download view, served as attachments | this repo |
| Container | Non-root (uid 10001), read-only root FS, `no-new-privileges`, only reachable on the internal `edge` network | this repo + home-server |

There is **no Cloudflare Access** in front of this site any more. If you find a
Zero Trust application covering `ella.molder.app`, delete it: while it exists
the hostname answers `302` to `<team>.cloudflareaccess.com` and the site looks
broken. See [ADR 0010](adr/0010-invitation-links-and-google-sign-in.md) for why
it went.

## How sign-on works

**Someone who already has an account:**

1. They open the site and press **Log ind**.
2. One tap on "Fortsæt med Google". No password, nothing to type.
3. They are in. The Django session lasts two weeks.

**Someone new:**

1. You send them an invitation link (see [operations.md](operations.md)). It
   looks like `https://ella.molder.app/invitation/<43 random characters>/`.
2. They open it. The page explains what Ella is and offers the same Google
   button. Opening the link is what permits the signup — the token is held in
   their session while they are away at Google.
3. Coming back from Google, their account is created from the Google profile
   (first name, email) and the invitation is marked used. They are signed in.
4. The link is now spent and answers `410` to anyone else.

Pressing "Fortsæt med Google" **without** an invitation gets the "du har ikke
adgang" page, whatever Google account is used. That is the whole access
control: there is no list of allowed addresses to maintain, and no address is
special.

Details worth knowing:

- Invitations are single-use, expire after 30 days
  (`DJANGO_INVITATION_VALID_DAYS`), and can be revoked before use.
- A token is 32 bytes from `secrets.token_urlsafe`, so guessing one is not a
  realistic attack. **Treat a link like a door code**: anyone holding it can
  create an account.
- `pre_social_login` attaches Google to an existing account with the same
  Google-verified email. That is what lets the `createsuperuser` admin account
  use your own Google address. Only provider-**verified** addresses match, so
  nobody can claim an account by typing its address somewhere.
- Session and CSRF cookies are `Secure`, the session cookie is `HttpOnly`,
  CSRF protection is on for all forms, and logout is POST-only.
- `X-Frame-Options: DENY`, and requests for any host other than
  `ella.molder.app` are rejected.
- Records are attributed to the signed-in account, not to a self-declared
  name ([ADR 0011](adr/0011-records-linked-to-accounts.md)).

## Known gaps (accepted)

| Gap | Why it is accepted | Revisit |
|---|---|---|
| Anonymous traffic reaches gunicorn | This is the price of dropping Access. There is no password form to attack except `/admin/`, which axes covers, and no inbound port or reachable origin IP | Turn on Bot Fight Mode and a rate-limiting rule (below) if the logs ever get noisy |
| Everyone signed in can edit and delete everything | Small, trusting group; recovery is from backups. Unlike before, a change can now be attributed ([ADR 0011](adr/0011-records-linked-to-accounts.md)) | If the group grows, or includes someone who should only read |
| No 2FA enforced by the site | It lives on the Google account instead, where most of the group already has it and where it is better managed than here | If a self-hosted provider arrives ([ADR 0009](adr/0009-self-hosted-identity-provider-deferred.md)) |
| A leaked invitation link is an account | Single use, 30-day expiry, revocable, 256 bits of randomness | Nothing to do; just do not post one publicly |
| Google is in the login path | Everyone in the group has an account. allauth supports several providers, so another can be added beside it | If someone joins without one |
| Nothing rate-limits the invitation URL | A wrong token is a cheap 404 and guessing one is infeasible | If the logs show someone trying |

## Cheap extra hardening at the edge

Both are zone settings in the Cloudflare dashboard for `molder.app`, not in
this repo, and neither is required:

- **Bot Fight Mode** (*Security → Bots*): drops the obvious scanners before
  they reach the tunnel.
- **One rate-limiting rule** (*Security → WAF → Rate limiting rules*); the free
  plan allows one. A sensible shape is: requests to `ella.molder.app/admin/*`,
  more than 10 in a minute from one IP, block for ten minutes. That puts a
  limit in front of the only password form instead of only behind it.

## Google OAuth client

One-time setup in the [Google Cloud console](https://console.cloud.google.com/).
The credentials go in `secrets/ella.sops.yaml` in home-server, never here.

1. Create a project (or reuse one). Name it something recognisable; the group
   sees it on the consent screen.
2. *APIs & Services → OAuth consent screen*: **External**, app name `Ella`,
   your email as support and developer contact. No scopes to add beyond the
   default profile/email.
   - Leave it in **Testing** only if you are willing to add each person as a
     test user — that is a list again, which is the thing we removed. Press
     **Publish app** instead. With only the default profile and email scopes,
     publishing needs no Google review.
3. *APIs & Services → Credentials → Create credentials → OAuth client ID*:
   - Application type: **Web application**
   - Name: `Ella`
   - Authorised JavaScript origin: `https://ella.molder.app`
   - Authorised redirect URI:
     **`https://ella.molder.app/accounts/google/login/callback/`**
     — the trailing slash matters, and this is the single most common thing to
     get wrong. A mismatch shows as Google's `redirect_uri_mismatch` error page
     and never reaches the site.
4. Copy the client ID and client secret into `secrets/ella.sops.yaml` as
   `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`.

For local development, add `http://localhost:8000` as an origin and
`http://localhost:8000/accounts/google/login/callback/` as a redirect URI on
the same client, and put the two values in your `.env`.

## HTTPS settings

Unchanged by ADR 0010; see [ADR 0005](adr/0005-tls-and-https-redirect-at-cloudflare.md).
In the dashboard for `molder.app`, under *SSL/TLS → Edge Certificates*:

- **Always Use HTTPS:** On.
- **HSTS:** On. This is a *zone* setting, so it applies to every proxied
  hostname on `molder.app`.

  | Setting | Value | Why |
  |---|---|---|
  | Max Age | 1 month at first, then 6 or 12 months once everything works | Browsers cache the policy for this long. A short value while testing keeps mistakes cheap |
  | Apply HSTS policy to subdomains | Off | A header sent by `ella.molder.app` only covers `*.ella.molder.app`, so turning this on gains nothing today. If the apex is ever served, it would force HTTPS on every `*.molder.app` name, including any LAN-only or plain-HTTP ones added later |
  | Preload | Off | Preload is baked into browsers and takes months to undo. It requires subdomains on, a 12-month max age and an apex that serves the header, and it locks every current and future subdomain to HTTPS. Not worth it for a private site |
  | No-Sniff header | On | Harmless and redundant: Django and Caddy already send `X-Content-Type-Options: nosniff` |

## Secrets

| Secret | Where it lives | Rotating it |
|---|---|---|
| `DJANGO_SECRET_KEY` | `secrets/ella.sops.yaml` in home-server, decrypted to `/etc/home-server/ella.env` | Edit with sops, commit, `make deploy SERVICE=ella`. Everyone is logged out of Django; nothing else breaks |
| `GOOGLE_OAUTH_CLIENT_SECRET` | same file | Create a new secret on the same OAuth client in Google Cloud, update sops, deploy. Existing sessions survive; only new logins use it |
| Invitation tokens | Rows in the database, backed up with it | Revoke the row, or let it expire |
| Admin password | Hashed in the SQLite DB | `changepassword`, see [operations.md](operations.md#resetting-the-admin-password) |

The image itself contains no secrets, which is why it is fine for the GHCR
package to be public.

## Checking it works

```bash
curl -sI https://ella.molder.app/           # 200, the public front page
curl -s  https://ella.molder.app/healthz/   # ok
curl -sI https://ella.molder.app/kalender/  # 302 to /accounts/login/
```

A `302` to `<team>.cloudflareaccess.com` from the first command means an Access
application still exists and has to be deleted.

Then open the site in a private window: the front page should be public, and
`/kalender/` should bounce you to a login page with a Google button and no
password field.

## If something goes wrong

- **A device or Google account is compromised:** in `/admin/`, untick
  **Active** on their user. That stops them at the next request. To end a
  session already in flight, rotate `DJANGO_SECRET_KEY`, which logs everyone
  out at once.
- **An invitation link went to the wrong person:** tick **Tilbagekaldt** on it
  in `/admin/`. It stops working immediately, including for someone who has
  already opened it but not yet finished signing in.
- **Google sign-in is broken** (expired secret, misconfigured client, Google
  outage): log in at `/admin/` with the superuser password and fix it from
  there. That is what the password login on `/admin/` is for.
- **Suspected leak of the secret key:** rotate `DJANGO_SECRET_KEY` (above).
  That invalidates every session.
- **Data deleted or vandalised:** restore the DB snapshot from restic
  ([deployment.md](deployment.md#restoring-the-database)). Records are
  attributed now, so the admin can show who did it.
