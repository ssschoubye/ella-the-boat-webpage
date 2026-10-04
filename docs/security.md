# Security and sign-on

## Layers

| Layer | What it does | Owned by |
|---|---|---|
| Cloudflare Tunnel | No inbound ports on the router or server, and the home IP is never published; only Cloudflare can reach Caddy | home-server |
| Cloudflare edge | TLS, "Always Use HTTPS", HSTS ([ADR 0005](adr/0005-tls-and-https-redirect-at-cloudflare.md)) | Cloudflare dashboard |
| **Invite-only sign-up** | An account can only be created by someone holding an unused invitation link, on the link's own page ([ADR 0014](adr/0014-invite-links-and-passwords.md)) | this repo |
| **django-axes** | Five failed logins locks out the IP, and the (email, IP) pair, for 30 minutes. The main defence, since the login page is public | this repo |
| Login wall | Every page requires a session except the public front page, the login page, the invitation page, `/admin/`, `/static/` and `/healthz/` ([ADR 0006](adr/0006-site-wide-login-wall-and-private-uploads.md), [ADR 0012](adr/0012-public-front-page.md)) | this repo |
| Private uploads | No `MEDIA_URL`; files only via the signed-in download view, served as attachments | this repo |
| Container | Non-root (uid 10001), read-only root FS, `no-new-privileges`, only reachable on the internal `edge` network | this repo + home-server |

There is **no Cloudflare Access** in front of this site. If you find a Zero
Trust application covering `ella.molder.app`, delete it: while it exists the
hostname answers `302` to `<team>.cloudflareaccess.com` and the site looks
broken. See [ADR 0010](adr/0010-invitation-links-and-google-sign-in.md) for why
it went.

There is also **no identity provider and no outbound email**. Sign-on depends
on nothing outside this container, which is the point of
[ADR 0014](adr/0014-invite-links-and-passwords.md); earlier designs used Google
and then Resend as well, and both are gone.

## How sign-on works

**Someone new:**

1. You send them an invitation link (see [operations.md](operations.md)). It
   looks like `https://ella.molder.app/invitation/<43 random characters>/`.
2. They open it and fill in a first name, any email address, and a password.
3. The account exists and they are signed in. Nothing is emailed, so there is
   nothing to wait for and no spam folder to check.
4. The link is now spent and answers `410` to anyone else.

**Someone who already has an account:** email address and password at
`/login/`. The session lasts two weeks.

That is the whole of it. There is no list of allowed addresses to maintain, and
no address is special.

Details worth knowing:

- **The signup form is on the invitation link itself.** There is no separate
  signup URL to leave open by accident — holding the token *is* the
  authorisation. The view re-checks the token on submit as well as on load, so
  a link revoked while someone sat on the open form does not work.
- Invitations are single-use, expire after 30 days
  (`DJANGO_INVITATION_VALID_DAYS`), and can be revoked before use. A token is
  32 bytes from `secrets.token_urlsafe`, so guessing one is not a realistic
  attack. **Treat a link like a door code**: anyone holding it can create an
  account.
- **The email address is the username.** It is lower-cased on signup and on
  login, so `Anton@` and `anton@` cannot become two accounts. It is **never
  verified** — the invitation link is the proof that this person is allowed in,
  and the address is only a label and a way to reach them. That is what removes
  any need for SMTP.
- Passwords go through Django's standard validators: minimum length, not a
  common password, not all numeric, not too similar to the name or address.
  They are hashed with PBKDF2.
- A rejected signup — mismatched passwords, address already taken, weak
  password — **does not spend the invitation**. There is a test for that.
- Session and CSRF cookies are `Secure`, the session cookie is `HttpOnly`,
  CSRF protection is on for all forms, and logout is POST-only.
- The `?next=` redirect after login only allows same-site URLs.
- `X-Frame-Options: DENY`, and requests for any host other than
  `ella.molder.app` are rejected.
- Records are attributed to the signed-in account, not to a self-declared name
  ([ADR 0011](adr/0011-records-linked-to-accounts.md)).

### Lockout behaviour

This is what stands between a public login page and someone working through a
password list, so it is worth knowing exactly:

- 5 failures locks both the **IP** and the **(email, IP) pair** for 30 minutes.
  The pair stops a slow grind against one account from several addresses; the
  bare IP stops one address working through every account.
- A locked-out client gets **`429`**, not `403`.
- The lockout **survives a subsequently correct password**. Otherwise the limit
  would only slow a guesser down until they landed it.
- Attempts are attributed using `CF-Connecting-IP`, which cloudflared sets and
  a client cannot forge, because nothing reaches this app except through the
  tunnel. Without that, every attempt would look like it came from Caddy's
  container IP and one attacker would lock out the whole group.
- `manage.py axes_reset` clears all lockouts.

## Known gaps (accepted)

| Gap | Why it is accepted | Revisit |
|---|---|---|
| **No self-service password reset** | There is no email, by design. A forgotten password is a minute in `/admin/` ([operations.md](operations.md#resetting-a-forgotten-password)). For six people that is cheaper than the SMTP, DNS records and secret rotation it replaces — but it is a recurring manual job, and the honest trade | If it becomes frequent, or the group grows |
| **A password is a weaker credential than an account with 2FA** | The login page is rate-limited, the content is a boat calendar and some insurance paperwork, and the realistic adversary is an opportunistic scanner rather than someone after this site. Credential reuse is a real risk that nothing here detects | If that assessment changes, the move is passkeys, not back to Google ([ADR 0014](adr/0014-invite-links-and-passwords.md)) |
| Anonymous traffic reaches gunicorn | The price of dropping Access. There is one form to attack and axes covers it, and there is no inbound port or reachable origin IP | Turn on Bot Fight Mode and a rate-limiting rule (below) if the logs get noisy |
| Everyone signed in can edit and delete everything | Small, trusting group; recovery is from backups, and a change can now be attributed ([ADR 0011](adr/0011-records-linked-to-accounts.md)) | If the group grows, or includes someone who should only read |
| No 2FA at all | There is no provider to enforce it, now that sign-on is self-contained | With passkeys, or a self-hosted provider ([ADR 0009](adr/0009-self-hosted-identity-provider-deferred.md)) |
| A leaked invitation link is an account | Single use, 30-day expiry, revocable, 256 bits of randomness | Nothing to do; just do not post one publicly |
| Nothing rate-limits the invitation URL | A wrong token is a cheap 404 and guessing one is infeasible | If the logs show someone trying |

## Cheap extra hardening at the edge

Both are zone settings in the Cloudflare dashboard for `molder.app`, not in
this repo, and neither is required:

- **Bot Fight Mode** (*Security → Bots*): drops the obvious scanners before
  they reach the tunnel.
- **One rate-limiting rule** (*Security → WAF → Rate limiting rules*); the free
  plan allows one. A sensible shape is: requests to `ella.molder.app/login/`
  and `/admin/*`, more than 10 in a minute from one IP, block for ten minutes.
  That puts a limit in front of the password form as well as behind it.

## HTTPS settings

See [ADR 0005](adr/0005-tls-and-https-redirect-at-cloudflare.md). In the
dashboard for `molder.app`, under *SSL/TLS → Edge Certificates*:

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

There is **one**, which is the main practical benefit of
[ADR 0014](adr/0014-invite-links-and-passwords.md).

| Secret | Where it lives | Rotating it |
|---|---|---|
| `DJANGO_SECRET_KEY` | `secrets/ella.sops.yaml` in home-server, decrypted to `/etc/home-server/ella.env` | Edit with sops, commit, push, `make deploy SERVICE=ella`. Everyone is logged out; nothing else breaks |
| Invitation tokens | Rows in the database, backed up with it | Revoke the row, or let it expire |
| Passwords | Hashed with PBKDF2 in the SQLite DB | `changepassword`, see [operations.md](operations.md#resetting-a-forgotten-password) |

The image itself contains no secrets, which is why it is fine for the GHCR
package to be public.

## Checking it works

```bash
curl -sI https://ella.molder.app/           # 200, the public front page
curl -s  https://ella.molder.app/healthz/   # ok
curl -sI https://ella.molder.app/kalender/  # 302 to /login/
```

A `302` to `<team>.cloudflareaccess.com` from the first command means an Access
application still exists and has to be deleted.

Then open the site in a private window: the front page should be public, and
`/kalender/` should bounce you to a login page asking for an email address and
a password.

## If something goes wrong

- **A device or account is compromised:** in `/admin/`, untick **Active** on
  their user. That stops them at the next request. To end a session already in
  flight, rotate `DJANGO_SECRET_KEY`, which logs everyone out at once.
- **An invitation link went to the wrong person:** tick **Tilbagekaldt** on it
  in `/admin/`. It stops working immediately, including for someone who already
  has the form open.
- **Someone forgot their password:** set a new one in `/admin/`
  ([operations.md](operations.md#resetting-a-forgotten-password)). Do not send
  a fresh invitation link — links only create new accounts, so that would give
  them a second one detached from their own bookings.
- **Someone is locked out:** they get a `429` and can wait 30 minutes, or
  `manage.py axes_reset` clears it.
- **Suspected leak of the secret key:** rotate `DJANGO_SECRET_KEY` (above).
  That invalidates every session.
- **Data deleted or vandalised:** restore the DB snapshot from restic
  ([deployment.md](deployment.md#restoring-the-database)). Records are
  attributed, so the admin can show who did it.
