# 0006. Site-wide login wall and private uploads

- **Status:** Accepted (recorded retroactively; in place since v1.0, 2026-09-17),
  amended by [ADR-0012](0012-public-front-page.md): the front page is public,
  and by [ADR-0015](0015-filarkiv-folders-and-inline-images.md): pictures are
  also shown inline, behind the same login
- **Date:** 2026-10-03

## Context
Everything on the site (the calendar, the maintenance board, the file
archive) is private to the group. Forgetting `@login_required` on one view
would leak it, and uploaded documents (insurance papers, receipts, manuals)
must not be reachable by a guessable URL.

## Decision
- `core.middleware.LoginRequiredMiddleware` requires an authenticated session
  for every path except the login page, `/admin/` (which has its own staff
  login), `/static/` and `/healthz/`. Views don't use `@login_required`.
- There is no `MEDIA_URL`, and nothing serves `MEDIA_ROOT` directly. Files
  are only downloadable through filarkiv's `download_file` view, as
  attachments. They're stored under a random UUID directory.

## Consequences
- New views are private by default. Making something public means adding it
  to `EXEMPT_PREFIXES`, which is deliberate and easy to review.
- Files are streamed by gunicorn rather than a static server. That's fine for
  occasional downloads up to the 25 MB upload limit.
- Serving files as attachments means an uploaded HTML/SVG file can't run
  script in the site's origin.
- This layer stays in place under Cloudflare Access ([0007](0007-cloudflare-access-in-front-of-the-site.md)).
  The two are independent defences.
- Access was later removed ([0010](0010-invitation-links-and-google-sign-in.md)),
  which makes this the outer defence rather than the inner one, and the
  front page was made public ([0012](0012-public-front-page.md)).
