# 0170 - account-hub: readable errors, self-service exits, admin basics

Status: accepted

Three small slices of the "Account Hub Refinements" milestone, decided with the maintainer on 2026-10-04 and grouped into one ADR the way [ADR 0081](0081-account-hub-campaign-roster-search-and-leave.md) grouped its three: each is a client-side addition against routes that already exist and are already authorized, so there is no design debate left beyond confirming what is built. **No `apps/api` change.** The fourth slice, invite links, has its own ADR ([0171](0171-account-hub-campaign-invite-links.md)), because it carries a deployment gate.

## Context

Checked against the source as it is now, not against the task description, which predates [ADR 0122](0122-api-client-package.md) and [ADR 0136](0136-account-hub-client-and-tenant-slug.md).

**Errors.** Failures already reach the pages as one `LorenzoApiError` (`@lorenzo/api-client`): `status`, the problem's `type`, the whole RFC 9457 body in `problem`, and a message of `detail`, else `title`, else `Request failed (n).`. About 45 places show it through `lib/errorMessage.ts`, which returns `error.message`. What that still gets wrong:

- A `422` body is `{title, type, status, errors: [{loc, msg, type}]}` and has no `detail`, so a person sees only the title ("Request Validation Error") and never which field.
- A `401` reads "Not logged in." or the API's own sentence, with nothing to press.
- A network failure is the browser's own `TypeError` ("Failed to fetch", "Load failed", ...).
- Anything else thrown, including a body that was not JSON, is shown as it came.

**Exits.** The API already lets a person leave on their own account, and records it in the activity log ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)): `DELETE /tenants/{t}/memberships/{me}` ([ADR 0036](0036-user-player-character-crud-api.md), a self-removal carve-out that needs no `OWNER`), `DELETE .../campaigns/{c}/gms/{me}` ([ADR 0034](0034-campaign-crud-api.md)), and `DELETE /me` (ADR 0036). The hub offers none of them. Only a library's owners see a remove control (`membershipAdminUi.ts`), so an organizer cannot leave; GM management is shown only to library administrators; nothing deletes an account.

**Admin basics.** A player can leave a campaign (ADR 0081) but nobody can remove one; a roster link can be made (ADR 0079) but not undone; a library's slug can be edited (ADR 0136) but not its name or description.

## Decision

### Readable errors

`src/lib/describeError.ts` exports `describeError(error: unknown): string` and `isSessionExpired(error: unknown): boolean`. It is pure, like `format.ts`: it imports `./apiError` (a re-export of `LorenzoApiError`) and nothing that reaches `@authgear/web`, so Vitest imports it as it does `format.ts`. It replaces `errorMessage.ts`, which is deleted, and every call site uses it. The first rule that applies wins:

| Error | Message |
| --- | --- |
| `ApiError`, status `401`; or an Authgear `invalid_grant` (a revoked or used-up refresh token, which the SDK throws after clearing the session) | "Your session has expired. Log in again." |
| `ApiError`, status `422` with an `errors` list | "Check what you entered: " and up to three `field (message)` entries joined by `; `, then `; and N more`. The field is the last name in `loc` (the `body`/`query` marker and list positions dropped, underscores as spaces); the message is the API's own, with its "Value error, " prefix and final full stop dropped and its first letter lower-cased. Entries it cannot read are skipped, and with none left the title is shown. |
| `ApiError` with a problem `detail`, else `title` | That text, as the API wrote it. |
| Network failure (`TypeError` whose message is a browser's fetch failure) | "Lorenzo couldn't be reached. Check your connection and try again." |
| Another `Error` or a string that does not look like JSON | Its own text: this app throws a few plain sentences on purpose ("Tenant editing is temporarily unavailable..."). |
| Anything else: no message, a body that starts with `{` or `[`, a non-error value | "Something went wrong. Try again in a moment." |

The structured data stays on `ApiError`, untouched. The API's own wording is not rewritten.

**A way back to login.** `src/lib/errorUi.ts` (the `*Ui.ts` shape of [ADR 0080](0080-account-hub-css-conventions-and-shared-dom-helpers.md)) exports `showError(target, error)`, which sets the text and, when `isSessionExpired`, adds a "Log in" button, and `errorLine(error)`, which returns a ready `<p class="error-text" role="alert">` for the places that append a line instead of setting one. A message that has to be a button's label, as in the inbox, uses `describeError` directly. `login()` remembers the page it was pressed on (`pathname` and `search`, never the fragment) in `sessionStorage`, and `/auth/redirect/` goes back to it instead of always home. The pure `safeReturnPath` in `src/lib/returnPath.ts` accepts only a plain path on this origin, refuses the `/auth/` pages themselves, and turns anything else into home; reading storage is allowed to fail. That is one small addition to `auth.ts` and the redirect page, and it is what lets a person whose session expired mid-task land where they were. It holds a path, never a token or an identifier.

### Leaving and deleting

`src/lib/exitsUi.ts` holds the three controls and `src/lib/exits.ts` the sentences they ask and say (pure, so tests hold them to what the API does). Each destructive action asks first with `window.confirm`, the pattern `characters.astro` already uses for "Leave this campaign": no typed phrase.

**Leave this library**, shown on every library where the caller's role is `owner` or `orga` (`TenantSummaryOut.role` from `GET /tenants`), calls `deleteMembership(tenant, me.id)`. A person who only plays or GMs there has no membership to leave; their way out is "Leave this campaign" on `/characters`. The confirmation says what ADR 0084 says happens: the tenant-wide membership ends, nothing they made is deleted, any campaign seat or GM role they hold there stays, and they get a notification confirming it. The control is separate from the owner-only "Remove" in the admins list, which stays as it is.

**Step down as GM**, shown wherever the caller is a GM (`campaignRoleFor(...) === 'gm'`, from `MeOut.campaign_gm_grants`), whether or not they administer the library, calls `revokeCampaignGm(tenant, campaign, me.id)`. There is no last-GM guard (ADR 0034): a campaign without a GM stays administrable by any library administrator.

**Delete your account**, in its own, clearly separated section at the foot of `/profile`, calls `DELETE /me` (`deleteAccount`) and then `logout()`. Its confirmation states what ADR 0036 and ADR 0084's addendum say, and no more: it deletes the caller's Lorenzo account; ends every membership, player seat, GM role and administrator opt-out they hold, in every library; and leaves what they created in place, no longer naming them. It does not delete their Authgear login, and logging in again creates a fresh, empty Lorenzo account.

**The sole owner.** Leaving a library and deleting an account both answer `409 LastOwnerError` when the caller is a library's only owner. `describeError` would show the API's `User <id> is the sole OWNER of tenant <id>`, so a pure helper, `soleOwnerMessage(error, libraryNames, exit)` in `src/lib/exits.ts`, recognizes a `409` whose `detail` has that shape, takes the library's id from it, and names it from the `listMyTenants()` names the page already has (fetched on demand from `/profile`): "You're the only owner of "<name>", so you can't leave it yet. Make someone else an owner first, then try again." (and "so your account can't be deleted yet" for the account). An id it cannot name becomes "one of your libraries". The API checks every owned library before deleting anything and names the first, so after one is fixed another may be named in turn.

The libraries' own word is **library**, in the buttons and the confirmations, not the maintainer's working word "tenant" ([docs/brand/identity.md](../brand/identity.md) §14.3, and what every other control on these pages already says).

### Admin basics

**Remove a player from a campaign** adds "Remove" to each player in the campaign roster view, for whoever passes `can_manage_campaign`: a library administrator or that campaign's GM. It calls the same `DELETE .../campaigns/{c}/players/{p}` as "Leave this campaign" (`removePlayer`; `leaveCampaign` calls it). Two details the roster alone does not give:

- A `PlayerRosterEntryOut` carries no player id, so the id comes from `GET .../campaigns/{c}/players` (`PlayerSummaryOut.id`, matched on `user_id` by `playerIdForUser`), read once per campaign the caller manages.
- The roster itself is a library administrators' read ([ADR 0081](0081-account-hub-campaign-roster-search-and-leave.md)), so a GM with no membership has none. They get the same list built from `GET .../players` instead (`rosterFromPlayers`), with the raw user id where a name would be. This is the one place the roster view widens, and only to what that GM can already read. (The `/beings` hand-off panel is a different matter: `GET .../beings` is itself a library admins' read, so a GM with no membership cannot reach it at all. That needs an `apps/api` change and is not part of this work.)

The confirmation names the consequence ADR 0081's does: the player's character links in that campaign go with the seat.

**Undo a roster link** is `DELETE /tenants/{t}/characters/{id}/players/{p}` (`unlinkCharacterFromPlayer`), the reverse of ADR 0079's reuse. `_authorize_roster_touch` lets the player whose row it is, or whoever can manage every campaign that player is in. So it appears in two places: next to "Use this character" on `/characters` ("Stop using in this campaign", on the caller's own seat) and on each character in the campaign roster, for managers. **It is never offered for a character's owner link.** A character's control comes from its roster rows (`controlled_character_entity_ids`), not from `owner_player_id`, so unlinking an owner would leave a character owned by someone who no longer controls it. `GET .../characters/{id}` gives `owner_player_id` and is open to any tenant participant, a player included. `/characters` reads it up front for the characters on the caller's own seats and shows the button only where it applies; in the campaign roster, where that would cost a request per character, the check is made when the button is pressed, and a refusal says why. Changing or clearing an owner is promotion and demotion, out of scope here.

**Edit a library** extends ADR 0136's slug editor to `name`, `slug` and `description`: `tenantSlugUi.ts` becomes `tenantEditUi.ts`, the button "Edit library", its form loading `GET /tenants/{t}` for the current description and ETag and sending `PATCH` with only what changed and `If-Match`. A stale edit and the slug rules and hint stay as ADR 0136 made them. Shown to owners and organizers, the same gate as `update_tenant` (`get_tenant_context`). A taken slug is a `409` problem the helper renders as the API wrote it.

## Not in scope

Deleting a campaign (destructive, and what to do with a campaign that has people in it needs a decision of its own); promoting or demoting characters, and changing a character's owner; group management; a wizard for handing over ownership; rewording the API's error text; a toast system; retries.

## Consequences

- `describeError`, `isSessionExpired`, `lastOwnerMessage` and the small pure helpers beside them are unit-tested in `tests/unit/`; the new controls are covered by logged-out page smoke specs as before and, where the real-API browser harness ([ADR 0136](0136-account-hub-client-and-tenant-slug.md)) can run, by specs against the real API.
- `errorMessage.ts` is gone; the ADR 0136 inline copy in the slug editor goes with it. A few places that showed an error in an odd spot now have a status line of their own (the inbox's "Mark read" no longer puts the message in the button's label; the bulk-invite send, which had no error handling at all, says what failed).
- `renderRenameableItem` takes `extras`, which come back after Cancel; an element appended to its row by hand is lost when the row swaps to its edit form.
- The slug editor's CSS classes are renamed `.tenant-details*`, and its spec follows: it is now a library editor, "Edit library".
- `login()` and the redirect page now share one `sessionStorage` key for a return path. It holds a path, never a token or an identifier.
- Leaving and account deletion are final from the hub's side: nothing here undoes them, and the activity log and the notification ADR 0084 added are the record.
- The roster view costs one extra read per campaign a person manages, to learn player ids. That is accepted, as ADR 0087 accepted duplicate reads between pages.
