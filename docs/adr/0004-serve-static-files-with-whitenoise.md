# 0004. Serve static files with WhiteNoise from the image

- **Status:** Accepted
- **Date:** 2026-10-03

## Context
With DEBUG off, Django doesn't serve CSS/JS. The old plan had Nginx serve
`staticfiles/`. On the home server, Caddy is a shared reverse proxy for every
site and has no access to files inside ella's image. The container's root
filesystem is also read-only.

## Decision
Run `collectstatic` at image build time and serve the result with WhiteNoise
(`CompressedManifestStaticFilesStorage`). The middleware and storage are
enabled only in `config.settings.prod`, so local development is unchanged and
doesn't warn about a missing `staticfiles/` directory.

## Consequences
- The image is self-contained: one artifact holds the code and the exact CSS/JS
  it was tested with, and rollback rolls both back together.
- File names are content-hashed and compressed, so they can be cached
  indefinitely.
- Caddy and home-server need no per-site static configuration.
- The manifest is strict. A `url()` in CSS pointing to a missing file fails
  `collectstatic`, and therefore the image build. A `{% static %}` tag pointing
  to a missing file raises an error (500) when that page renders in production,
  even though it renders fine in development. After adding a static file, build
  the image or run `collectstatic` with prod settings to catch it.

## Alternatives considered
- **Caddy serving a synced static directory:** needs a second artifact kept in
  step with the image, plus a home-server change for every static change.
- **A separate Nginx sidecar:** more moving parts for the same result.
