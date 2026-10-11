# 0268 - Personal access tokens: the API

Status: accepted

## Context

Programs that act for a person, the `lorenzo` command line first and a Discord bot later, hold an Authgear access token that lasts minutes and is renewed with a refresh token ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)). That works for a person at a keyboard. It does not suit a script, a server, or a machine with no browser, and it ties every program to Authgear's client registration. The v1.0 checklist asks for "personal access tokens with a device-style link" ([v1.0](../../v1.0.md)).

Decided with the maintainer: the **device-code flow** ([RFC 8628](https://www.rfc-editor.org/rfc/rfc8628)) to hand one out; a token **acts as its owner, whole** (no scopes); **no expiry** unless the owner sets one when approving; **revocable**, and **listed** with a name and when it was last used.

Authentication today ([ADR 0023](0023-authgear-token-verification.md), [ADR 0027](0027-authgear-cloud-not-self-hosted.md)): `get_current_user` verifies an Authgear JWT against the JWKS, upserts the `app_user` row by `sub`, and attaches the roles of the token's claim (`authgear_roles`, [ADR 0033](0033-tenant-creation-and-update-api.md)) for the two role gates. Everything else (memberships, seats, GM grants) is read from the database by user id, so any credential that resolves to a `User` row has "the same permissions as that user" for free.

## Decision

**Two user-level tables**, in migration `b9d1e47a3c62`. Neither stores tenant data, so neither has `tenant_id` or row-level security, the footing of `app_user` and `user_profile_picture` ([ADR 0022](0022-user-tenant-membership.md), [ADR 0056](0056-profile-pictures.md)), and neither belongs in `copyable_tables.py` (its test lists tables with a `tenant_id` and RLS). The bearer lookup that resolves a token runs before any identity is known, so there is no `app.user_id` for a policy to key on; what a caller may see is enforced by the routes (`WHERE user_id = me`) and tested for cross-user reads.

- `personal_access_token`: `id`, `user_id` (cascades with the account), `name` (1 to 80 characters), `token_hash` (unique), `token_hint` (the secret's last four characters, to tell two tokens of one name apart), `created_at`, `last_used_at`, `expires_at` (null: never), `revoked_at`.
- `device_authorization`: a pending approval. `device_code_hash` (unique), `user_code` (unique), `client_name` (what the device calls itself), `status` (`pending`, `approved`, `denied`), the approver's `user_id`, the chosen `token_name` and `token_expires_at`, `expires_at` (ten minutes), `last_polled_at`.
- `app_user.last_seen_roles`: see "Permissions" below.

**The secret.** `lor_pat_` followed by `secrets.token_urlsafe(32)` (256 random bits). Only its SHA-256 is stored. A fast hash is right for a secret that is already high-entropy; the lookup is an indexed equality on the hash, so there is no secret-versus-stored comparison to time. The secret exists in memory at minting and in the one response that carries it. The pending row never holds it: the first poll that finds the request approved mints the token and deletes the request in one transaction (`SELECT ... FOR UPDATE`, so two concurrent polls cannot mint two). A lost response means connecting again.

**The flow** (RFC 8628, answers as problem details whose `type` is the name):

- `POST /device-codes` (unauthenticated, body `{client_name?}`, `201`) returns `device_code` (long, opaque, only its hash is kept), `user_code` (eight consonants shown `ABCD-EFGH`: no vowels so no words, no `0/O/1/I`), `verification_uri` (the account hub's `/device`, from the `ACCOUNT_HUB_URL` setting), `verification_uri_complete` (`...?code=ABCD-EFGH`), `interval` (5 seconds) and `expires_in` (600).
- `POST /device-codes/token` (unauthenticated, body `{device_code}`): `200` with `{access_token, token_type, id, name, expires_at}` once; otherwise `400` with `authorization-pending`, `slow-down` (polled inside the interval), `device-code-expired` (unknown, used and past its time all answer the same) or `access-denied`.
- `GET /me/device-codes/{user_code}` shows a signed-in person what is asking (`client_name`, `expires_at`); `POST .../approve` takes `{name, expires_at?}` (an expiry must be in the future); `POST .../deny`. Codes are accepted in any case with or without the dash. An approval can only be made for a request that is still pending and unexpired (`404` otherwise).
- `GET /me/tokens` lists the caller's tokens that are not revoked (an expired one is listed, marked `is_expired`); `DELETE /me/tokens/{id}` revokes (idempotent; another user's id is `404`). At most 50 active tokens per person.

**Verification.** `verify_token` hands a bearer that starts with `lor_pat_` through without touching the JWKS, and `get_current_user` resolves it: hash, look up, require not revoked and not expired, load the user, apply the suspension check ([ADR 0057](0057-platform-operations.md)), set `app.user_id`. An unknown, revoked or expired token is the usual `401` with one message. `last_used_at` moves with a conditional `UPDATE` at most once every five minutes, so a busy token is not a write per request.

**A token manages nothing about tokens.** A request authenticated by a token carries `user.via_personal_token`; the dependency `InteractiveUser` refuses it with `403` (`personal-token-forbidden`) on approve, deny, preview, list and revoke, and on `DELETE /me`. A leaked token can therefore neither mint a second token nor revoke the owner's other tokens' ability to be revoked, nor delete the account; it ends when the owner revokes it from a signed-in session. Everything else it may do as the owner.

**Permissions.** A token resolves to the owner's `User` row, so memberships, seats and grants are the owner's. Authgear roles are the one thing not in the database. The roles of every interactive token are now remembered in `app_user.last_seen_roles` (written by the upsert that already runs on each request). A token carries the **tenant-creator** role if the owner's last interactive token did, so `lorenzo tenant create` works with one. It **never** carries the platform-operator role: `/admin/*` needs a signed-in session. Staleness is the cost: a role withdrawn in Authgear stays on a token until its owner next signs in somewhere; revoking the token is the remedy, and the role is a creation right, not access to anything existing.

**Abuse limits.** The two unauthenticated routes use the token-bucket backstop of [ADR 0092](0092-campaign-invite-links.md) under a setting of their own (`DEVICE_RATE_LIMIT_PER_MINUTE`, 60, shared by the two, keyed by client address with the same trusted-proxy-hops rule). The signed-in routes that look a code up are limited per user (`DEVICE_LOOKUP_RATE_LIMIT_PER_MINUTE`, 20), since a code is about 2.6 times 10 to the 10th and lives ten minutes: this stops a signed-in account walking the space. The edge rule is still the real control ([invite-link rate limiting](../operations/invite-link-rate-limiting.md)).

**Logging, not the activity log.** The activity log ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)) is per library (`tenant_id` is required) and excludes `/me`; a token belongs to no library, so there is no entry to write. Creation and revocation are structured log events (`personal_token_created`, `personal_token_revoked`, with the ids, never a secret). A user-level audit trail would be a table of its own and is not built.

## Consequences

- Any program can be given the owner's whole account without Authgear involvement, and the owner can see and end each one. A token that is not revoked and has no expiry works indefinitely: that is the decision, and the hub's list shows "last used" so a forgotten one is noticed.
- The API depends on one more table lookup per token request, indexed on the hash.
- Existing clients are untouched: a bearer that is not `lor_pat_` takes the old path. `DELETE /me` now needs a signed-in session.
- `/device-codes` joins the unauthenticated surface (with `/invites/{token}`); both are rate-limited in-process and expected to have an edge rule before going live.
- Revoked rows are kept (they hold no secret); pruning them, and abandoned `device_authorization` rows (they are deleted when polled after expiry, otherwise they stay), is a later chore.
- A deploy sets `ACCOUNT_HUB_URL` (the workflow defaults it to the official hub).
- The account hub and the CLI are in [ADR 0269](0269-personal-access-tokens-hub-and-cli.md).
