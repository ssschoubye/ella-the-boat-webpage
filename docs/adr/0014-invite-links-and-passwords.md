# 0014. Invitation links and a password, and nothing else

- **Status:** Accepted
- **Date:** 2026-10-04
- **Supersedes:** [0010](0010-invitation-links-and-google-sign-in.md), [0013](0013-email-sign-in-codes.md)

## Context
[ADR 0010](0010-invitation-links-and-google-sign-in.md) replaced Cloudflare
Access with Google sign-in behind single-use invitation links.
[ADR 0013](0013-email-sign-in-codes.md) then added emailed one-time codes, so
that people without a Google account were not shut out.

Each step was defensible on its own, and together they produced a sign-on
system that, for a six-person boat calendar, cost more than it was worth:

- a Google Cloud project, an OAuth consent screen to publish, and a redirect
  URI that fails obscurely if a trailing slash is wrong;
- a Resend account, DNS records on `molder.app` that must never be tidied
  away, and an API key to rotate;
- two third parties in the login path, two extra secrets in sops, and a
  failure mode where email sign-in breaks silently while Google keeps working,
  so the person who notices is the one who needed it;
- `django-allauth` and its socialaccount extras, with `SOCIALACCOUNT_ONLY`
  deliberately off and a comment warning the next person not to "fix" that.

The owner's reaction, on being given the setup checklist, was to ask why it
could not just be an invitation link where someone picks an email and a
password. That is the right question, and the answer is that it can.

What the earlier ADRs were really avoiding was a **public login page with no
rate limiting**, which ADR 0007 correctly called out. But `django-axes` was
installed in ADR 0010 and is already configured. The prerequisite had been met;
the elaborate part had stopped earning its place.

## Decision
One way in. An invitation link opens a form; the person enters a name, any
email address, and a password; the account exists and they are signed in.

- **The signup form lives on the invitation link itself.** There is no
  separate signup URL that could be left open by mistake. Holding the token
  *is* the authorisation, and the view re-checks it on the POST as well as the
  GET, so a link revoked while the form sat open does not work.
- **The email address is the username**, lower-cased on the way in and on the
  way out so `Anton@` and `anton@` cannot become two accounts. It is **never
  verified**: the invitation link is the proof that this person is allowed in,
  and the address is only a label and a way to reach them. That is what
  removes the need for SMTP entirely.
- **Passwords go through Django's standard validators** — minimum length, not
  a common password, not all numeric, not too similar to the name or address.
- **django-axes is now the defence that matters.** Five failures locks out
  both the IP and the (username, IP) pair for thirty minutes, reading
  `CF-Connecting-IP` because every request arrives via cloudflared and Caddy.
  It answers `429`, and the lockout survives someone subsequently guessing
  correctly — otherwise the limit would only slow an attacker down until they
  landed it.
- **`django-allauth` is removed**, along with `django.contrib.sites`, the
  Google provider, both adapters, the `user_signed_up` receiver, and eleven
  templates. `django-axes` stays. Requirements drop from six packages to five,
  and transitively lose PyJWT, cryptography, requests and oauthlib.
- Everything else is untouched: the public front page
  ([0012](0012-public-front-page.md)), the login wall
  ([0006](0006-site-wide-login-wall-and-private-uploads.md)), records
  attributed to accounts ([0011](0011-records-linked-to-accounts.md)), and
  `/admin/` as the break-glass path.

## Consequences
- **Adding a person is still: send a link.** Unchanged, and still no list of
  allowed addresses anywhere. What changed is that it now needs no dashboard
  anywhere either.
- Setting the site up needs **one secret**, `DJANGO_SECRET_KEY`. No OAuth
  client, no SMTP relay, no DNS records, nothing to verify, nothing to rotate
  on a schedule.
- **No self-service password reset**, because there is no email. A forgotten
  password is a message to the owner and a minute in `/admin/`. For six people
  that is cheaper than the machinery it replaces — but it *is* a recurring
  manual task, and the honest trade this ADR makes.
- **The credential is weaker.** A password chosen by someone not thinking
  about passwords is weaker than a Google account with 2FA, and credential
  reuse is a real risk nothing here detects. Against that: the login page is
  rate-limited, the content is a boat calendar and some insurance paperwork,
  and the realistic adversary is an opportunistic scanner rather than someone
  who wants this specific site. If that assessment ever changes, the move is
  passkeys (below), not back to Google.
- **A leaked invitation link is still an account**, mitigated by single use, a
  30-day expiry, revocation, and 256 bits of randomness.
- Nothing about sign-on depends on a third party any more, so nothing about it
  can break because someone else changed something. That also means nothing to
  reconfigure during a migration.
- Four ADRs now describe sign-on, three of them superseded. The live ones are
  this and [0012](0012-public-front-page.md); 0007, 0010 and 0013 are history.
  That is a lot of churn in one day, and worth remembering as an argument for
  starting at the simple end.

## Alternatives considered
- **Keep Google only** ([0010](0010-invitation-links-and-google-sign-in.md)).
  Strongest credential and no passwords to manage, but it requires everyone to
  have a Google account and the owner to maintain an OAuth client.
- **Keep Google plus emailed codes** ([0013](0013-email-sign-in-codes.md)).
  Covers everyone and still has no passwords, at the price of two vendors, two
  secrets, DNS records and a silent partial-failure mode. This is what was
  actually built and then removed; the code is in the history if it is ever
  wanted back.
- **Passkeys.** No passwords, no provider, no SMTP, phishing-resistant, and
  one tap on a modern phone — strictly better than a password on every axis
  except familiarity and device loss. The best candidate if passwords ever
  become a problem, and worth revisiting then rather than now.
- **Email verification on signup, without SMTP.** Impossible, and pointless
  here: the invitation link already establishes that the person is allowed in,
  which is the only thing verification would have been proving.
