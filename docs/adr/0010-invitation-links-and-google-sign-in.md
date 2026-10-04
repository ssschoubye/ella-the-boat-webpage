# 0010. Invitation links and Google sign-in, instead of Cloudflare Access

- **Status:** Accepted
- **Date:** 2026-10-04
- **Supersedes:** [0007](0007-cloudflare-access-in-front-of-the-site.md)

## Context
[ADR 0007](0007-cloudflare-access-in-front-of-the-site.md) put Cloudflare
Access in front of the whole site, with the Django login kept behind it. In
use that turned out to cost more than it was worth:

- **Three lists of people.** The Access Allow policy, the Django `User` table,
  and `BOOKER_CHOICES` in `booking/models.py`. Adding a person meant editing
  all three, and the third one is a code change, `makemigrations` in three
  apps and a deploy ([operations.md](../operations.md) step 3).
- **Two logins.** An emailed six-digit code, then a username and password.
  ADR 0007 recorded this as "the main annoyance".
- **Passwords that only the owner can manage.** No self-service reset by
  design, so every forgotten password is a message to the owner and a
  `changepassword` on the server.

The group is about six people who already have Google accounts. None of this
protects anything the group does not already trust each other with; it is just
work.

The requirement, stated by the owner: as frictionless as possible, without
maintaining an approved list of users.

## Decision
Drop Cloudflare Access for this site. Sign-on becomes **Google, through
django-allauth, with signup gated on a single-use invitation link**:

- `SOCIALACCOUNT_ONLY` is on and there are no password fields anywhere in the
  site. There is no password to reset, so there is nothing to reset.
- `adgang.Invitation` is a single-use, expiring link. Visiting it parks the
  token in the session; `adgang.adapters.InvitationOnlySocialAccountAdapter`
  allows a signup only while a usable one is held, and spends it on success.
  Invitations are minted in `/admin/` or with `manage.py invite "<name>"`.
- Nobody is ever listed in advance. Sending the link **is** granting access,
  and the account exists from the moment it is used.
- Removing a person is deactivating their account, which is per-person and
  takes effect immediately.
- `pre_social_login` attaches Google to an existing account with the same
  provider-verified email, so the `createsuperuser` break-glass admin can use
  the owner's own Google address without colliding.
- `/admin/` keeps its password login as the way back in if Google or allauth
  breaks. **django-axes** locks out an IP after 5 failures for 30 minutes,
  which ADR 0007 named as the prerequisite for removing Access.

The front page becomes public so there is somewhere to put the login button
([0012](0012-public-front-page.md)), and the person fields become real
accounts ([0011](0011-records-linked-to-accounts.md)) — that third list was
half the problem.

## Consequences
- Adding a person is: send a link. Nothing to edit, nothing to deploy.
- One tap to sign in, no code to copy out of an inbox, no password.
- **Anonymous traffic now reaches gunicorn.** This is the real cost of
  dropping Access, and the honest summary is that the site is now defended by
  the login wall ([0006](0006-site-wide-login-wall-and-private-uploads.md)),
  axes on `/admin/`, and the fact that there is no other form to attack. The
  Cloudflare Tunnel still means no inbound ports and no reachable origin IP.
  Cloudflare's Bot Fight Mode and a free-plan rate-limiting rule are listed in
  [security.md](../security.md) as the next cheap layer.
- **A leaked invitation link is an account.** Mitigated by single use, a 30-day
  expiry, revocation, and 256 bits of randomness in the token. Send them the
  same way you would a door code.
- Google is now in the login path. Anyone without a Google account cannot get
  in; that is true of everyone in the group today. If it stops being true, an
  email one-time-code provider can be added alongside, because allauth
  supports several.
- Access policies no longer have to be remembered during a migration, and
  nothing about sign-on lives in a dashboard any more. The Zero Trust
  application should be **deleted**, not just loosened — as long as it exists
  it intercepts the hostname and the site returns a 302 that looks like a
  tunnel fault.
- Two new dependencies to keep current: `django-allauth` and `django-axes`.
  allauth is the one that matters, because it sits in the login path.
- The 2FA that the emailed PIN provided is gone from the site itself. It moves
  to the Google account, where most of the group already has it, and where it
  is better managed than here. Recorded as a known gap in
  [security.md](../security.md).

## Alternatives considered
- **Keep Access, make it the only login** (verify the signed
  `Cf-Access-Jwt-Assertion` in Django and auto-create the user). Removes the
  double login and two of the three lists for about 80 lines of middleware.
  Rejected because it keeps an Allow policy that has to be edited per person,
  which is the specific thing being removed, and keeps sign-on in a dashboard
  that no migration or backup covers.
- **Access with an Allow policy for any verified email.** No list at all and
  no code, but it lets anyone on the internet who can read their own inbox
  into the file archive. That is identity capture, not access control.
- **A self-hosted identity provider** ([0009](0009-self-hosted-identity-provider-deferred.md)).
  Still the right answer when a second and third app need shared logins; still
  far too much machinery for one site and six people. Nothing here is wasted
  when that day comes: allauth speaks OIDC, so the provider becomes another
  entry in `SOCIALACCOUNT_PROVIDERS`.
- **Magic links sent by email from Django.** No Google dependency, but it
  needs SMTP, a deliverability problem, and a link in an inbox is a weaker
  credential than a Google session with 2FA on it.
