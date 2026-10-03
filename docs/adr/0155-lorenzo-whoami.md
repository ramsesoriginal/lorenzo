# 0155 - `lorenzo whoami`

Status: accepted

Follow-up to [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md). Part of the set decided together on 2026-10-03 ([ADR 0153](0153-lorenzo-version.md)).

## Context

`lorenzo login` ends with "Signed in.", which says a token was stored, not that the API accepts it. A token from `LORENZO_TOKEN` or `--token-stdin` is never checked at all until some other command happens to use it. After a login, a changed `LORENZO_API_URL`, or an Authgear client being set up, the useful question is "does this actually work, and as whom?", and the only way to ask it was to run a command that did real work.

## Decision

```bash
lorenzo whoami [--json]
```

It calls `GET /me` with whichever token the CLI would use, and prints:

- **who you are**: your user id, and your display name, nickname and email where set;
- **which API** it asked;
- **where the token came from**: `--token-stdin`, `LORENZO_TOKEN`, or the stored login (the same order [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md) fixes);
- **how many tenants** you hold a membership in.

`--json` prints `GET /me`'s answer as it came, for a script.

- **A rejected token is said plainly**: on a `401` the message names the source of the token and what to do (run `lorenzo login`, or fix `LORENZO_TOKEN`). Any other API refusal, such as a suspended account, shows its own detail.
- **It is the smoke test for a login.** `login` then `whoami` is the shortest check that an Authgear client, the API's issuer and the CLI agree.
- **One thing it does besides read:** the first `GET /me` for a new Authgear subject creates their user row ([ADR 0023](0023-authgear-token-verification.md)). That is true of every first call, from any client, so `whoami` doesn't avoid it.

## Not in scope

- **Roles and capabilities.** `GET /me` does not say whether you hold `tenant-creator` ([ADR 0033](0033-tenant-creation-and-update-api.md) named exposing it as a deferred follow-up), so `whoami` can't either. When the API grows `/me` capabilities (it's on the v1.0 list), `whoami` should show them, and `tenant create` could stop guessing.
- **Listing the tenants.** That is [ADR 0154](0154-lorenzo-tenant-list.md).

## Consequences

- A new operation, `GET_ME`, joins the client's table of operations, with the usual test against the dumped schema.
- Someone setting up a client for the first time has one command that shows whether it worked.
