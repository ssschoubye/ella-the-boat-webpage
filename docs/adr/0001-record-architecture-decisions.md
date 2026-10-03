# 0001. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-03

## Context
Ella started as a Django starter template and grew into a small app shared by
the people who own the boat. Moving it from "runs on a laptop" to "runs on the
home server, on the internet" required a run of decisions about hosting,
storage, backups and sign-on. Several of them only make sense once you know
the alternatives and the size of the group (about six people). Without a
record, the reasons would be lost, and future changes would undo them by
accident or re-argue them from scratch.

## Decision
Keep Architecture Decision Records in `docs/adr/`, one Markdown file per
decision, numbered in order, in the format given in [README.md](README.md).
Decisions made before ADRs were introduced, such as [0006](0006-site-wide-login-wall-and-private-uploads.md), are recorded retroactively.

## Consequences
- Anyone changing hosting, storage or auth reads the relevant ADR first, and
  writes a superseding one if they change course.
- The other files in `docs/` describe how things *are*. ADRs describe *why*.
