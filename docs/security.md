# Security and sign-on

## Layers

| Layer | What it does | Owned by |
|---|---|---|
| Cloudflare Tunnel | No inbound ports on the router or server, and the home IP is never published; only Cloudflare can reach Caddy | home-server |
| Cloudflare edge | TLS, "Always Use HTTPS", HSTS ([ADR 0005](adr/0005-tls-and-https-redirect-at-cloudflare.md)) | Cloudflare dashboard |
| **Invite-only sign-up** | An account can only be created while holding an unused invitation link ([ADR 0010](adr/0010-invitation-links-and-google-sign-in.md)) | this repo |
| **Google sign-in** | No passwords for the group; the credential is their Google account, with whatever 2FA they have on it | this repo + Google Cloud |
| **Email sign-in codes** | The same, for anyone without a Google account: a one-time code to any address ([ADR 0013](adr/0013-email-sign-in-codes.md)) | this repo + Resend |
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

There are **two ways in**, and the choice is the person's. Both are gated by
the same invitation link, and neither involves a password.

**Someone who already has an account:**

1. They open the site and press **Log ind**.
2. Either one tap on "Fortsæt med Google", or they type their email address
   and press "Send mig en kode", then enter the code that arrives.
3. They are in. The Django session lasts two weeks.

**Someone new:**

1. You send them an invitation link (see [operations.md](operations.md)). It
   looks like `https://ella.molder.app/invitation/<43 random characters>/`.
2. They open it. The page explains what Ella is and offers both options.
   Opening the link is what permits the signup — the token is held in their
   session while they are away at Google, or while the code is in flight.
3. **Google:** their account is created from the Google profile (first name,
   email) and they are signed in.
   **Email:** they enter an address, get a verification code, type it in, and
   the account is created. They are signed in.
4. Either way the invitation is now spent and answers `410` to anyone else.

Signing up **without** an invitation is refused on both paths — Google gets
the "du har ikke adgang" page whatever account is used, and the signup form
is closed. That is the whole access control: there is no list of allowed
addresses to maintain, and no address is special.

**Which should you tell people to use?** Google, if they have it: the
credential is an account with 2FA on it rather than an inbox. The email code
exists so that not having Google is never a reason someone cannot see the boat
calendar.

Details worth knowing:

- Invitations are single-use, expire after 30 days
  (`DJANGO_INVITATION_VALID_DAYS`), and can be revoked before use.
- Sign-in codes look like `TSPC-CKMW`, last 10 minutes, and die after three
  wrong attempts. Asking for one is limited to 3 per minute per address and
  20 per minute per IP (allauth's defaults).
- Nobody has a password: accounts are created without one
  (`ACCOUNT_SIGNUP_FIELDS` omits it), so they have an unusable password hash
  and there is nothing to reset or guess. The `/admin/` superuser is the one
  exception.
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
| **An inbox is now a credential** | Anyone who can read a member's email can get a code and sign in. The same was true of Cloudflare Access's one-time PIN, which this replaced, so it is no reason to go back &mdash; but it is weaker than Google with 2FA, which is why people are pointed at Google first | If the archive ever holds something that warrants more |
| **The site depends on outbound email** | Only for the code route. If Resend is down or the key expires, Google keeps working and `/admin/` is still the way in, so it degrades rather than locks everyone out | The symptom is in the container logs; see below |
| Resend sees who signs in and when | The address and the code pass through them. The same trust is already extended to Cloudflare for every request | If self-hosted mail ever becomes worth the deliverability work |
| Nothing rate-limits the invitation URL | A wrong token is a cheap 404 and guessing one is infeasible | If the logs show someone trying |
| Rate limits are per gunicorn worker | They live in the default LocMemCache, so the per-minute limits are effectively doubled across two workers. The limit that matters &mdash; three wrong codes &mdash; is in the session, so brute-forcing a code is bounded anyway | Move the cache to the database if a third worker appears |

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

## Sending the codes: Resend

One-time setup at [resend.com](https://resend.com). The free tier is 3,000
emails a month, against perhaps twenty here. The credentials go in
`secrets/ella.sops.yaml` in home-server, never in this repo.

1. Sign up, then **Domains → Add Domain** → `molder.app`.
2. Resend shows a handful of DNS records (a DKIM `TXT`, an SPF `TXT`, and
   usually a `MX` for the return path). Add them in the Cloudflare dashboard
   for `molder.app`, under *DNS → Records*.
   - Set these records to **DNS only** (grey cloud), not proxied. Proxying a
     DKIM or SPF record breaks verification.
   - **Do not delete them later.** Nothing on the site will mention them, and
     removing them during a tidy-up silently breaks the email sign-in route
     while Google keeps working.
3. Wait for the domain to read **Verified**. Cloudflare DNS is usually a
   minute or two.
4. **API Keys → Create API Key**, with *Sending access* only. Copy it now; it
   is shown once. It looks like `re_...`.
5. Put the values in `secrets/ella.sops.yaml`:

   ```yaml
   DJANGO_EMAIL_HOST: smtp.resend.com
   DJANGO_EMAIL_PORT: "587"
   DJANGO_EMAIL_HOST_USER: resend
   DJANGO_EMAIL_HOST_PASSWORD: re_xxxxxxxxxxxx
   DJANGO_DEFAULT_FROM_EMAIL: Ella <noreply@molder.app>
   ```

   The username is the literal string `resend`; the API key is the password.
   The sender address must be on the verified domain or Resend rejects the
   message.

Locally you need none of this: the default backend prints the mail to the
`runserver` output, so the code is in your terminal.

### Checking Resend works

On the server, with the container running:

```bash
docker exec -it -u app ella python manage.py sendtestemail you@example.com
```

If that raises, the SMTP settings are wrong. If it succeeds but nothing
arrives, the domain is not verified or the sender is off-domain. Resend's
dashboard shows every attempt and why it was rejected.

Do not test this by asking for a sign-in code with an address that has no
account: that is deliberately indistinguishable from success on screen, and
the mail it sends says "no such account".

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
| `DJANGO_EMAIL_HOST_PASSWORD` (Resend API key) | same file | Create a new key in Resend, update sops, deploy, delete the old key. Only the email sign-in route uses it |
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
  outage): people can use the email code route instead, and you can log in at
  `/admin/` with the superuser password. That is what the password login on
  `/admin/` is for.
- **Email codes stop arriving:** check the container logs for an SMTP error,
  then Resend's dashboard. The usual causes are an expired or deleted API key
  and a DNS record that was removed from `molder.app`. Google sign-in is
  unaffected, so the site will not look broken to most of the group &mdash;
  which is exactly why it can go unnoticed.
- **Suspected leak of the secret key:** rotate `DJANGO_SECRET_KEY` (above).
  That invalidates every session.
- **Data deleted or vandalised:** restore the DB snapshot from restic
  ([deployment.md](deployment.md#restoring-the-database)). Records are
  attributed now, so the admin can show who did it.
