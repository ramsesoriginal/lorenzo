# 0290 - The flips as routes and the visibility switch

Status: accepted, decided with the maintainer on 2026-10-14. Slice D5 of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md), tracked in #718. Builds on [ADR 0289](0289-the-flip-rules-and-the-bridge-skew-gate.md) (the rules, as functions), [ADR 0287](0287-who-may-read-a-public-repository.md) (who may read a public repository) and [ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md) (the profile and its `visibility`).

## Context

[ADR 0289](0289-the-flip-rules-and-the-bridge-skew-gate.md) made the rules that hold when a repository goes between private and public, and left them as functions of a session: nothing in the API could call them, and `PATCH .../profile` refused `public`. [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §7 and slice D5 make them routes and give the Owner a switch in Studio ([RFC 0036](../rfcs/0036-repository-tooling.md) T7). The same RFC says `public` becomes accepted when D2 to D6 are in, and D3 (Discover), D4 (the preview) and D6 (the gates before launch: delisting, the cooldown, quotas, the terms line) are not built.

## Decision

### Routes that exist and a switch that is off

`GET /tenants/{id}/flip-check`, `PUT /tenants/{id}/public` and `DELETE /tenants/{id}/public` exist and are tested, and **a deployment setting, `public_repositories_enabled`, decides whether a repository can be made public**. It is off, so `PUT` answers `422 public-repositories-not-available` ("Public repositories are not available yet. This repository stays private.") and changes nothing, not even a summary sent beside it. The flip-check says `available: false` for Studio to hide the switch. The setting is turned on for a deployment when the gates of RFC 0038 §6 are in and the maintainer says so; nothing else in the code changes then. `DELETE` and `GET` answer whether or not it is on: making a repository private is the safe direction, and a repository that is public must be able to leave.

### `GET .../flip-check`

What a flip would run into, before it is asked, for the dialog: `available`, the `visibility`, whether there is a summary, the repositories it is built on that are not public (each with whether the caller owns it, so the dialog can offer to make it public) or are behind, the public repositories built on it, how many libraries hold a grant they gave themselves by copying it (`public_libraries`) and how many it invited (`invited_libraries`, whom it keeps). Owner only, and it writes nothing.

### `PUT .../public`

Takes what `PUT .../published` takes (`label`, `notes`, `breaking`, `acknowledge_breaking`) and two more: `summary` and `preview`. It is `make_public` of ADR 0289 in one transaction, with what RFC 0038 §7 adds:

- **A summary is required**, sent here or already on the profile: `422 public-repository-summary-required`. A visitor reads it in Discover and on the repository's page. Until the profile screens of T5 exist, the dialog asks for it.
- **The preview switch is set with the flip**: `off`, `showcase` or `public`, `showcase` unless the Owner chooses ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §5: the default is a choice the Owner saw). It only says what a visitor may look at before copying; the routes that read it are D4's.
- The rest is ADR 0289: every repository it is built on public (`409 built-on-not-public`) and up to date (`409 built-on-behind`), the first public release with its document, and nothing written if anything is refused. The answer is the same as a publish's: the repository and its release.

### `DELETE .../public`

`make_private` of ADR 0289: `409 public-repositories-built-on-it` while a public repository is built on it, `409 public-copies-would-be-cut-off` with the number until `?acknowledge_revokes=true`, then the self-given grants are revoked, the libraries told and the visibility changed. It answers how many were revoked. A query parameter and not a body, so a client that sends none sends nothing.

### The profile no longer changes the visibility

`PATCH .../profile` with a `visibility` other than the repository's own is `422 visibility-has-its-own-route`, in the same request as everything else in it, so nothing is kept. Before this slice the refusal was `public` alone, because `private` could only be a no-op; with a public repository it would have made it private without a release, a notice or a revoke. Saying what it already is stays allowed.

### Deleting a public repository

The rule is ADR 0184's, unchanged: no grant may remain, and the grants libraries gave themselves count. The refusal now says how many of them are those and to make the repository private first, which revokes them after the warning.

### What a flip does not yet say

The terms line the Owner agrees to, the account that will be shown as publisher and the warning about GM-only text in what a library copies are the gates of RFC 0038 §6 (D6) and the dialog's words; the route takes nothing for them yet. The warning about GM-only text is the dialog's.

## What the tests pin

- Without the switch: `PUT` refused in words and nothing kept; with it: a repository goes public with a release that is current and kept, its summary and preview set, the libraries that read it live told, and any signed-in user reads it.
- A summary is required, and one already on the profile counts; the preview defaults to `showcase`; already public is `409`.
- A bridge is refused while what it is built on is private, the check names each with whether the caller owns it, and the stack goes public upstream first with the bridge taking their releases.
- Only the Owner flips: a stranger gets the `404` of any other tenant, and the audit of routes lists all three as the Owner's.
- Going private: told the number first, then the self-given grant gone and the invited one kept and reading live, the copier cut off and keeping its copy; refused while a public repository is built on it.
- The profile cannot flip a repository, and a public repository with copies is not deleted.

## Not in scope

- **Discover, the preview routes, the gates before launch, the terms line and deprecate**: D3, D4, D6 and D8, and the setting stays off until they are in.
- **The profile screens** (T5).
- **The Studio switch**, in the hub, below.

## Consequences

- The API can make a repository public and private, with every rule of RFC 0037 §6 and RFC 0038 §7, and a deployment cannot do it by accident: the setting is one line to turn on.
- Nothing can change a repository's visibility except these two routes.
- No migration.
