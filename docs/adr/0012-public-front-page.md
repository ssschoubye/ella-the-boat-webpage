# 0012. A public front page

- **Status:** Accepted
- **Date:** 2026-10-04
- **Amends:** [0006](0006-site-wide-login-wall-and-private-uploads.md)

## Context
[ADR 0006](0006-site-wide-login-wall-and-private-uploads.md) made every path
require a session, so an anonymous visitor to `https://ella.molder.app` got a
redirect to a login form and nothing else.

With Cloudflare Access in front ([0007](0007-cloudflare-access-in-front-of-the-site.md))
that was invisible: nobody reached Django without already being allowed.
Removing Access ([0010](0010-invitation-links-and-google-sign-in.md)) makes
the front page the first thing anyone sees, including someone who has just
been handed an invitation link and wants to check the site is what they were
told it is.

## Decision
`/` is public. `core.views.home` renders `core/landing.html` for anonymous
visitors and the existing `core/home.html` for everyone signed in — same URL,
no redirect, no bookmark to change.

- `core.middleware.LoginRequiredMiddleware` gains `EXEMPT_PATHS`, matched
  **exactly**, because `"/"` as a prefix would exempt the whole site. That
  distinction is the only subtle thing here and is the reason the two lists
  are separate.
- The landing page says what Ella is, that it is private, and how to get in.
  It deliberately carries nothing about the boat: no names, no documents, no
  plans, no calendar. A test asserts it links to none of the private sections.
- `base.html` hides the navigation and the logout button for anonymous
  visitors and shows "Log ind" instead, since the header is now rendered for
  people who cannot open any of those links.

## Consequences
- Everything except `/`, the sign-on flow, `/admin/`, `/static/` and
  `/healthz/` is still private by default, which is the property ADR 0006
  exists to protect. Making something else public is still a deliberate,
  reviewable edit to one of two lists in one file.
- The front page is a public page on a home server, so it is the one URL that
  gets scanned and crawled. It is a static template with no query parameters
  and no database access.
- Anything added to the landing template is public. That is easy to forget, so
  the template says so in a comment at the top and the test pins it.

## Alternatives considered
- **Keep the whole site behind the wall**, with the login page as the de facto
  front page. Fewer moving parts, and it was the right answer while Access was
  in front. Rejected because the first thing a new person sees would then be a
  bare Google button with no indication of what they are signing in to.
- **Move the app under a `/app` prefix and serve the landing page at `/`.**
  Tidier separation, and it was the shape planned when Access was going to be
  scoped to a path. Rejected now that Access is gone: it buys nothing and
  changes every URL in the site, including ones people have bookmarked.
