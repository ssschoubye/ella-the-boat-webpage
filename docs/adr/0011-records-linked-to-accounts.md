# 0011. Records are linked to accounts

- **Status:** Accepted
- **Date:** 2026-10-04
- **Supersedes:** [0008](0008-records-are-not-linked-to-user-accounts.md)

## Context
[ADR 0008](0008-records-are-not-linked-to-user-accounts.md) kept the "who"
fields — `Booking.booker`, `ArchiveFile.uploaded_by`, `Ticket.created_by`,
`Comment.author` — as a `CharField` with choices from a hardcoded
`BOOKER_CHOICES` list in `booking/models.py`, imported by the other two apps.
It named its own revisit conditions, and two of them have now happened:

- Everyone has a real account, created by signing in with Google
  ([0010](0010-invitation-links-and-google-sign-in.md)).
- That list was the third of the three lists of people that ADR 0010 set out
  to remove, and the worst of them: adding a person meant editing code,
  generating migrations in three apps, and deploying.

It was also the weakest link in the attribution: the "who" was a dropdown, so
anyone could book, upload or comment as anyone else, including by accident.

## Decision
Replace all four fields with a `ForeignKey` to the user model, and **remove
them from the forms entirely**. The views set them from `request.user`:

- `on_delete=models.SET_NULL, null=True`. Deleting an account must never take
  the boat's booking history with it.
- Templates render a person through `core.templatetags.people.person`, which
  prefers the first name from Google, falls back to the email local part, and
  renders a missing account as "Ukendt".
- Editing an existing record does not reassign it, so correcting a date does
  not rewrite who booked the trip.
- The migrations are written by hand rather than generated: a generated
  `AlterField` from `CharField` to `ForeignKey` asks SQLite to cast
  `"person_1"` to an integer. They rename the old column aside, fill the new
  one from it where an account's first name matches, and only then drop it.

## Consequences
- `BOOKER_CHOICES` is gone. Adding a person is sending an invitation link, and
  no longer touches this repo at all.
- The recorded person is now always the real one, and there is a usable audit
  trail — the gap ADR 0008 accepted. `/admin/` can filter by person on all
  three apps.
- One less field to fill in on every form.
- Still **no per-user permissions**: everyone signed in may edit and delete
  everything. That half of ADR 0008 stands, for the same reason — six people
  who trust each other — and recovery is still from the nightly backup
  ([0003](0003-sqlite-on-a-bind-mount-with-snapshot-backups.md)). What changed
  is that a destructive edit can now be attributed.
- Records made before this change have no account to point at and read as
  "Ukendt" unless an account's first name happened to match the old label.
  Ella had not been deployed when this landed, so in practice there were none.
- A deactivated account still shows its name on old records, which is what you
  want when someone leaves.

## Alternatives considered
- **Keep the choice field and add a FK alongside it**, writing both. Safer for
  old rows, but it leaves two sources of truth for the same fact and the
  dropdown stays on the form, so the spoofing problem stays too.
- **A `Person` model separate from `User`**, so someone can be named on a
  booking without having an account. Worth doing if the boat is ever lent to
  people who should not get a login; today it would just be ADR 0008's
  hardcoded list with extra steps.
