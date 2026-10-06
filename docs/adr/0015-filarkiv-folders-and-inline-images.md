# 0015. Filarkiv folders, and pictures shown in the browser

- **Status:** Accepted
- **Date:** 2026-10-06
- **Amends:** [0006](0006-site-wide-login-wall-and-private-uploads.md)

## Context
The file archive was one flat list, and every file was served as an
attachment ([ADR 0006](0006-site-wide-login-wall-and-private-uploads.md)).
Most uploads are photos of the boat, and looking at one meant downloading it
and opening it somewhere else. The list also mixed photos with manuals and
insurance papers.

Serving attachments only was a security decision: an uploaded HTML or SVG
file opened in the browser would run script in the site's origin, with the
viewer's session.

## Decision
- **Folders.** `Folder` is a tree. The top level holds exactly two fixed
  folders, Billeder and Filer (`root_key`), which can't be renamed or
  deleted. Anyone signed in can create, rename and move files between
  folders, and delete an empty folder. Deleting a folder with contents is
  for staff accounts (`is_staff`) only, and removes the whole subtree and its
  files from disk. Files and folders point at their parent with `PROTECT`,
  so "empty only" also holds at the database level.
- **Existing files** were sorted by migration 0006: JPG, JPEG, PNG, GIF and
  WEBP into Billeder, everything else into Filer.
- **Pictures are shown inline**, through two new signed-in views:
  `<pk>/vis/` (the original) and `<pk>/miniature/` (a 480 px JPEG thumbnail).
  Only the five raster types above are ever served inline; every other file,
  SVG included, still only downloads as an attachment, and the inline URL
  answers 404 for it. Inline responses carry a `Content-Type` from a fixed
  map, never a guess, `X-Content-Type-Options: nosniff`, and
  `Content-Security-Policy: default-src 'none'; sandbox`.
- **Thumbnails** are made with Pillow on upload and stored next to the
  original. A file Pillow can't read just has no thumbnail.
  `manage.py make_thumbnails` backfills any that are missing.
- A folder's pictures are a grid; clicking one opens a viewer
  (`static/js/lightbox.js`) with arrows, keys and swipe.

## Consequences
- Pillow is a new dependency, with manylinux wheels, so the image still
  builds without system packages.
- A raster image renders inline but can't run script; the CSP and sandbox
  cover a browser that mis-sniffs one as a document anyway.
- Thumbnails take a little more space under `/data/media` and are covered by
  the same backups.
- Inline responses are cacheable privately for a day, since a record's file
  never changes after upload.
- HEIC photos are download-only, since most browsers can't show them.
  iPhones usually convert to JPEG when uploading through a browser.

## Alternatives considered
- **Serve all files inline.** Would let an uploaded SVG or HTML file run
  script with a signed-in viewer's session.
- **Scale the originals in the browser** instead of thumbnails: no new
  dependency, but a folder of 5 to 25 MB phone photos is slow on a phone.
- **A separate picture section** next to the archive: two places to look
  for things, and no home for documents that belong with a trip's photos.
