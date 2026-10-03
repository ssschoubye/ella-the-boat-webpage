# Security and sign-on

## Layers

| Layer | What it does | Owned by |
|---|---|---|
| Cloudflare Tunnel | No inbound ports on the router or server; only Cloudflare can reach Caddy | home-server |
| Cloudflare edge | TLS, "Always Use HTTPS", HSTS ([ADR 0005](adr/0005-tls-and-https-redirect-at-cloudflare.md)) | Cloudflare dashboard |
| **Cloudflare Access** | Only listed email addresses get past the edge, via a one-time PIN sent by email ([ADR 0007](adr/0007-cloudflare-access-in-front-of-the-site.md)) | Cloudflare dashboard |
| Django login wall | Every page requires a Django session except the login page, `/admin/` (staff-only login), `/static/` and `/healthz/` ([ADR 0006](adr/0006-site-wide-login-wall-and-private-uploads.md)) | this repo |
| Private uploads | No `MEDIA_URL`; files only via the logged-in download view, served as attachments | this repo |
| Container | Non-root (uid 10001), read-only root FS, `no-new-privileges`, only reachable on the internal `edge` network | this repo + home-server |

## How sign-on works

1. Someone opens `https://ella.molder.app`. If Cloudflare doesn't have a valid
   Access session for them, it shows its own login page.
2. They enter their email. If it's on the Allow list, Cloudflare emails a
   6-digit code. Entering it gives them an Access session (`CF_Authorization`
   cookie) for the configured session duration.
3. The request now reaches Django, which shows the ella login page. They log in
   with their Django username and password. The session lasts 2 weeks
   (Django's default).
4. Logging out of ella ends the Django session. The Access session lasts until
   it expires or is revoked in the dashboard.

Django details:
- Passwords are hashed with PBKDF2 and checked against Django's standard
  validators when set through the admin.
- Session and CSRF cookies are `Secure`, and the session cookie is `HttpOnly`.
- CSRF protection is on for all forms, and logout is POST-only.
- The `?next=` redirect after login only allows same-site URLs.
- `X-Frame-Options: DENY`, and requests for any host other than
  `ella.molder.app` are rejected.

There is no self-service sign-up or password reset. People are added and
reset by an admin ([operations.md](operations.md)).

## Known gaps (accepted)

| Gap | Why it's accepted | Revisit |
|---|---|---|
| No rate limit or lockout in Django's login | Cloudflare Access stops anonymous traffic before it reaches Django | If Access is ever removed, add `django-axes` first |
| Everyone logged in can edit and delete everything, and the "who" fields are self-declared | Small, trusting group; recovery is from backups | [ADR 0008](adr/0008-records-are-not-linked-to-user-accounts.md) |
| Two logins (Cloudflare, then Django) | Simplest setup; each layer works on its own | Verify the `Cf-Access-Jwt-Assertion` JWT in Django and drop the second login ([ADR 0007](adr/0007-cloudflare-access-in-front-of-the-site.md)) |
| No 2FA inside Django | The emailed PIN acts as the second factor | With a self-hosted identity provider ([ADR 0009](adr/0009-self-hosted-identity-provider-deferred.md)) |

## Secrets

| Secret | Where it lives | Rotating it |
|---|---|---|
| `DJANGO_SECRET_KEY` | `secrets/ella.sops.yaml` in home-server, decrypted to `/etc/home-server/ella.env` | Edit with sops, commit, `make deploy SERVICE=ella`. Everyone is logged out of Django; nothing else breaks |
| Django passwords | Hashed in the SQLite DB | `changepassword`, see [operations.md](operations.md#resetting-a-password) |
| Access allow list | Cloudflare Zero Trust dashboard | Edit the policy |

The image itself contains no secrets, which is why it's fine for the GHCR
package to be public.

## Cloudflare Access setup

This is done once, in the Cloudflare dashboard under **Zero Trust**. Menu
paths below were checked against Cloudflare's docs on 2026-10-03; Cloudflare
moves them occasionally, but the concepts stay the same.

1. **Enable Zero Trust** for the account if it isn't already. Choose a team name
   (it becomes `<team>.cloudflareaccess.com`) and the **Free** plan. Cloudflare
   may ask for a payment method even for the free plan.
2. **Add One-time PIN as a login method:** *Zero Trust → Integrations →
   Identity providers → Add new identity provider → One-time PIN*.
   - Organizations created since mid-2026 **don't get One-time PIN
     automatically**. Their default login method is the *Cloudflare identity
     provider*, which only works for people with a Cloudflare account, so it's
     no use for the boat group. Add One-time PIN even if the list isn't empty.
   - No SMTP setup is needed on our side. Codes come from
     `noreply@notify.cloudflare.com`, are valid for 10 minutes and work once.
     Cloudflare only sends one if the address is allowed by a policy. If
     someone doesn't get theirs, check their spam folder.
3. **Main application:** *Zero Trust → Access controls → Applications →
   Create new application → Self-hosted and private*.
   - Name: `Ella`
   - *Add public hostname*: domain `molder.app`, subdomain `ella`, empty path
   - Policy: create one named `Bådfolk`, action **Allow**, Include →
     **Emails** → the group's addresses. Applications deny everything by
     default, so only the people listed here get in. An *Access group* with
     those emails is tidier if other apps will reuse it.
   - Login methods: select **only One-time PIN**, and untick the Cloudflare
     identity provider if it's listed. With a single method you can also turn
     on **Apply instant authentication**, which skips the "choose a login
     method" screen.
   - Session duration: e.g. `1 month`. Shorter means more emailed codes.
4. **Health check bypass:** create a second *Self-hosted and private*
   application.
   - Name: `Ella healthz`
   - Public hostname: `ella.molder.app`, path `healthz`
   - Policy: action **Bypass**, Include → **Everyone**

   The more specific path wins, so `/healthz/` stays reachable for the
   blackbox probe. It only ever returns `ok`.
5. **HTTPS settings** ([ADR 0005](adr/0005-tls-and-https-redirect-at-cloudflare.md)):
   in the main dashboard for `molder.app`, under *SSL/TLS → Edge Certificates*.
   Django relies on Cloudflare for both of these.
   - **Always Use HTTPS:** On.
   - **HTTP Strict Transport Security (HSTS):** this is a *zone* setting, so it
     applies to every proxied hostname on `molder.app`, not just ella.

     | Setting | Value | Why |
     |---|---|---|
     | Enable HSTS | On | |
     | Max Age | 1 month at first, then 6 or 12 months once everything works | Browsers cache the policy for this long. A short value while testing keeps mistakes cheap |
     | Apply HSTS policy to subdomains | Off | A header sent by `ella.molder.app` only covers `*.ella.molder.app`, so turning this on gains nothing today. If the apex is ever served, it would force HTTPS on every `*.molder.app` name, including any LAN-only or plain-HTTP ones added later |
     | Preload | Off | Preload is baked into browsers and takes months to undo. It requires subdomains on, a 12-month max age and an apex that serves the header, and it locks every current and future subdomain to HTTPS. Not worth it for a private site |
     | No-Sniff header | On | Harmless and redundant: Django and Caddy already send `X-Content-Type-Options: nosniff` |

     Revisit subdomains and preload only if `molder.app` itself starts serving
     a site and every subdomain is guaranteed to be HTTPS.
6. **Check it**:
   ```bash
   curl -sI https://ella.molder.app/          # 302 to <team>.cloudflareaccess.com
   curl -s  https://ella.molder.app/healthz/  # ok
   ```
   Then open the site in a private window and log in with a listed email.
7. In home-server, point the blackbox probe at `https://ella.molder.app/healthz/`
   ([deployment.md](deployment.md#5-docs)).

## If something goes wrong

- **A device or inbox is compromised:**
  - remove the email from the Access policy;
  - revoke their sessions (*Zero Trust → Team & Resources → Users*, select
    them, then *Action → Revoke → Revoke sessions*);
  - set their Django account inactive.
- **Suspected leak of the secret key:** rotate `DJANGO_SECRET_KEY` (above).
  That invalidates every Django session and password-reset token.
- **Data deleted or vandalised:** restore the DB snapshot from restic
  ([deployment.md](deployment.md#restoring-the-database)).
