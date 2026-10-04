# 0013. Email sign-in codes alongside Google, sent through Resend

- **Status:** Accepted
- **Date:** 2026-10-04
- **Extends:** [0010](0010-invitation-links-and-google-sign-in.md)

## Context
[ADR 0010](0010-invitation-links-and-google-sign-in.md) made Google the only
way in, and listed the obvious gap as a known one: "Anyone without a Google
account cannot get in; that is true of everyone in the group today. If it
stops being true, an email one-time-code provider can be added alongside,
because allauth supports several."

The owner asked for that now, before anyone is actually locked out. The
pressure is mild but real:

- A Google account is not the same thing as a `@gmail.com` address — anyone
  can create one on an `@outlook.com` or work address — so nobody is strictly
  excluded today. But *requiring* someone to create a Google account to see a
  boat calendar is exactly the friction this design set out to remove.
- Adding Microsoft as a second provider was considered and rejected: it moves
  the boundary rather than removing it, and leaves anyone on a small ISP or a
  Google-less company domain in the same position.

ADR 0010 rejected emailed credentials partly to avoid SMTP. That reasoning
assumed Google-only was sufficient, and it is the part that no longer holds.

## Decision
Add a second way in: a **one-time code emailed to any address**, through
allauth's `ACCOUNT_LOGIN_BY_CODE_ENABLED`. Both ways are gated by the same
invitation link, so the access model of ADR 0010 is unchanged.

- **Signing up** (new person, invited): the invitation page offers Google *or*
  an email field. The email path creates the account via
  `/accounts/signup/` with `ACCOUNT_SIGNUP_FIELDS = ["email*"]` — no password
  field at all — and `ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED` makes them
  prove they own the address with a code before the account is usable.
- **Signing in** (returning): Google, or "send me a code" at
  `/accounts/login/code/`.
- **`SOCIALACCOUNT_ONLY` is now off**, because it disables the whole local
  account machinery. What keeps passwords out is `ACCOUNT_SIGNUP_FIELDS`
  omitting them, so accounts are created with an unusable password and there
  is still nothing to reset.
- **Both adapters gate signup.** `InvitationOnlyAccountAdapter` was previously
  a hard `return False`; it now checks for a pending invitation exactly as the
  social one does. Getting this wrong would have been the hole in the gate, so
  a test asserts both refuse together.
- Spending the invitation moved out of the social adapter's `save_user` into a
  `user_signed_up` receiver (`adgang/signals.py`), which fires on both paths.
  One place, identical behaviour.
- **Sending** is Django's SMTP backend pointed at **Resend** (3,000 mails a
  month free, far more than six people logging in occasionally), with
  `molder.app` verified so codes come from `noreply@molder.app`. Credentials
  live in `secrets/ella.sops.yaml` in home-server. Locally the backend
  defaults to the console, so development needs no SMTP and the code appears
  in the `runserver` output.

Codes, not magic links: a code can be read off a phone and typed into the
laptop whose browser is already open, and it cannot be silently followed by a
mail client or link-scanner the way a one-click link can.

## Consequences
- Nobody is excluded by which email provider they use, which is the whole
  point. Google stays as the one-tap path for those who have it.
- **The site now depends on outbound email.** If Resend is down, the API key
  expires, or the DNS records are removed, the email route stops working while
  Google keeps going — a partial failure that is easy to miss. The symptom is
  in the container logs; `/admin/` remains the break-glass way in either way.
- A third-party sees the sign-in metadata (who logged in, when). Resend sees
  the address and the code. That is a real disclosure and it is accepted: it is
  the same trust already extended to Cloudflare for every request.
- One more secret to rotate, and two DNS records on `molder.app` that must not
  be deleted during some future tidy-up.
- **Email is now a credential.** Someone with access to a member's inbox can
  get in. That was also true of Cloudflare Access's one-time PIN, which this
  design replaced, so it is not a regression — but it is weaker than a Google
  account with 2FA, and the group should be told to use Google if they have it.
- allauth's default rate limits do the throttling: 3 code requests per minute
  per address, 20 per minute per IP, and 3 wrong codes before the attempt is
  dead. django-axes does not see these, because code entry never calls
  `authenticate()`.
- The request-a-code form never reports failure, by design
  (`ACCOUNT_PREVENT_ENUMERATION`): an unknown address gets a "no such account"
  email instead, so the page cannot be used to discover who has an account.
  That email deliberately does not link to the signup page, since signing up
  needs an invitation anyway.

## Accepted gaps
- **Rate limits live in the default LocMemCache**, which is per-gunicorn-worker,
  so the per-minute limits are effectively doubled across two workers. The
  limit that actually matters — three wrong codes — is held in the session, not
  the cache, so brute-forcing a code is bounded regardless. Revisit by moving
  the cache to the database if a third worker ever appears.
- **No bounce handling.** A code mailed to a typo'd address simply never
  arrives; the person asks for another.

## Alternatives considered
- **Microsoft as a second provider.** No SMTP, no DNS, no new secret. Rejected
  as above: it relocates the problem.
- **Passkeys** (`MFA_PASSKEY_SIGNUP_ENABLED`, already available in allauth). No
  provider, no SMTP, phishing-resistant, and genuinely one tap. Rejected as the
  *primary* fallback because losing the device loses access unless recovery
  codes are kept, and it is the hardest flow to explain over the phone. Still
  the best candidate if the email dependency becomes annoying.
- **Gmail SMTP with an app password.** Zero signup and no DNS, but codes arrive
  from a personal address, it needs 2FA on that account to mint the password,
  and it ties the site's logins to one person's mailbox. Rejected for a
  verified `molder.app` sender, which is also trivial to swap back to — it is
  the same four `EMAIL_*` settings.
- **Self-hosting SMTP.** Deliverability from a home IP through a tunnel is a
  project, not a setting.
