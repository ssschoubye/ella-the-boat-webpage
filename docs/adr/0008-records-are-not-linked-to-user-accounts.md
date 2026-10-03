# 0008. Records are not linked to user accounts (for now)

- **Status:** Accepted
- **Date:** 2026-10-03

## Context
Bookings (`booker`), archive files (`uploaded_by`), tickets (`created_by`) and
ticket comments (`author`) record a person by picking from
`booking.models.BOOKER_CHOICES`. That's a hardcoded list of names, separate
from Django's `User` accounts. Every logged-in user can create, edit and
delete everything. So anyone can book "as" someone else, and nothing records
who actually made a change.

Linking these fields to `User` would mean a data migration (mapping names to
accounts), changing all four apps' forms and templates, and deciding who may
edit or delete what.

## Decision
Keep the current model. Among six people who trust each other, the "who" field
is a label, not an access control. Access to the site as a whole is controlled
by [0006](0006-site-wide-login-wall-and-private-uploads.md) and
[0007](0007-cloudflare-access-in-front-of-the-site.md).

## Consequences
- No per-user permissions and no audit trail. A mistaken or malicious delete
  can't be attributed. Recovery is from the nightly backup
  ([0003](0003-sqlite-on-a-bind-mount-with-snapshot-backups.md)).
- Adding or renaming a person requires a code change to `BOOKER_CHOICES` and a
  deploy ([operations.md](../operations.md#adding-a-person)). The stored
  values (`person_1`…) stay stable, so renaming a label is safe. Reordering or
  reusing keys is not.

## Revisit when
- someone needs to know who changed or deleted something;
- the group grows or includes people who shouldn't be able to edit everything;
- a self-hosted identity provider arrives ([0009](0009-self-hosted-identity-provider-deferred.md)),
  which makes real per-person accounts natural.

At that point, replace the choice fields with foreign keys to `User` that
default to `request.user`, and keep the old value in a migration.
