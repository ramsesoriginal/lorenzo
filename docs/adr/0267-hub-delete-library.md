# 0267 - Account hub: deleting a library

Status: accepted

## Context

`DELETE /tenants/{id}` exists since [ADR 0184](0184-deleting-a-tenant.md): a tenant Owner whose account holds the platform tenant-creator role deletes the tenant and everything in it, refused with `409 repository-still-granted` while other tenants hold a grant on a repository. That ADR gave it a CLI command and left the hub out ("it isn't given a button"). The v1.0 row "tenant deletion" ([v1.0.md](../../v1.0.md)) needs a person who runs a library to be able to remove it without the CLI. The maintainer decided on a button in the hub.

## Decision

- **A "Delete this library" section** in the Admins tab of a library on `/tenants`, and the same section, as "Delete this repository", in the People tab of a repository in Studio. It is one component (`TenantDelete`) used by both; the noun follows the kind ([ADR 0178](0178-account-hub-repositories.md)).
- **Who sees what.** An Owner whose account may delete (`/me` `capabilities.create_tenant`, the same platform permission, [ADR 0175](0175-me-says-what-you-may-create.md)) sees the button. An Organizer, who edits the library, sees the reason instead: "Only an Owner can delete this library." An Owner whose account lacks the permission is told that deleting also needs it. Anyone else sees nothing. The API still decides; a refusal that gets through is shown in words.
- **A dialog says what is lost** before anything happens: the library's name, that there is no undo, and counts of campaigns, entries and people with a role. The campaigns and people come from the reads the tab already made; the entries are one request for a page of one (`GET .../entities?size=1`, its total). A count that could not be read is left out, not shown as zero.
- **Typing the name opens the button.** The last button is disabled until the field holds exactly the library's name (spaces around it do not count). Escape or Cancel closes the dialog, leaves nothing deleted, empties the field and puts the focus back on the button; the dialog is a native modal `<dialog>`, so focus stays inside while it is open. While the request is on its way it cannot be closed.
- **A refusal is shown in the dialog, in plain words.** `repository-still-granted` becomes "Other libraries still draw on this repository, so it can't be deleted yet. On the Libraries using it tab, stop inviting each of them, then try again. Libraries that already copied it keep their copies."; the two 403s say who may delete, and anything else is described by the hub's usual error text. The dialog stays open, so the Owner can fix it and press the button again.
- **On success** the hub's cache is emptied, the page reads the list again, opens the first remaining library (or repository) and shows "Deleted library "name"." where the person lands. The message goes away on the next navigation.
- **No new API and no new request but the entry count.** No new abuse limit is added (see below).

## Not in scope

- **Abuse limits.** The maintainer decided that the invite-link rate-limit backstop ([ADR 0092](0092-campaign-invite-links.md)) is enough for v1; nothing more is built.
- A grace period, an undo, a way to export first (the runbook of [ADR 0085](0085-tenant-data-export-audit-and-runbook.md) stands).

## Consequences

- ADR 0184's "account hub isn't given a button" no longer holds; the rest of that ADR stands.
- The button shows only for an account with the platform permission, so a plain Owner of a library cannot delete it from the hub, the same as through the API. If that proves too narrow, the permission is the thing to revisit, not this page.

## Tests

- Unit (`tests/unit/deleting.spec.ts`): who is offered what, the lost-lines, the name match, and each refusal in words.
- Against the real API (`tests/real-api/tenant-deletion.spec.ts`, in `test:real-api:ci`): an Owner deletes a library after typing its name and lands on the list with the message, and the cache does not bring it back after a reload; a wrong name or case keeps the button disabled; Escape closes and returns the focus; an Organizer has the reason and no button; an Owner without the account permission is told why; a repository other libraries draw on is refused in words and goes once the invitation is withdrawn.
