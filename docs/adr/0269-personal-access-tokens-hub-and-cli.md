# 0269 - Personal access tokens: the account hub and the command line

Status: accepted

## Context

[ADR 0268](0268-personal-access-tokens-api.md) adds the API: a device asks for a code, a signed-in person approves it, the device is handed a `lor_pat_` token, and the person can list and revoke their tokens. This ADR is the two clients: where the person approves and manages, and the first program that uses a token.

## Decision

**Account hub** ([ADR 0071](0071-account-hub-stack-auth-deploy.md)):

- **`/device`, "Connect a device".** Reads `?code=` (what `verification_uri_complete` carries) and shows the request: what is asking (the device's own name), the code, a name for the token (prefilled with the device's name, 80 characters), and when it stops working: **Never** (the default), in 30 days, in 90 days, in a year. Connect or Deny. Without a code in the address, or with one that has run out, there is a box to type it (any case, dash optional). A code that is wrong or used up gets one sentence saying so and that they last ten minutes. The page asks for no referrer, since its address holds a live code. A person who is not signed in gets the hub's usual "Log in" and comes back to the same address.
- **"Personal access tokens" on `/profile`** (the section is `#personal-access-tokens`): one row per token with its name, the last four characters, when it was made, "Never used" or "Last used" and when, "Never expires" or when it expires (an expired one is marked), and **Revoke** behind a confirmation that names it. The secret is never shown there; it was only ever shown to the device.
- Wording follows [the identity guide](../brand/identity.md) §14.3: "device", "personal access token", "library" where a library is meant; nothing says "tenant" or "OAuth".
- Pure helpers (code normalization, expiry presets, texts) are in `lib/personalTokens.ts` with unit tests; the calls are in `lib/personalTokensApi.ts`; a real-API spec (`tests/real-api/personal-tokens.spec.ts`, in `test:real-api:ci`) runs the flow in a browser against the real API: approve with a name and an expiry, the device polling (pending, slow down, token), the token working, the list, revoke, typing a code, denying.

**Command line** (`apps/cli`, [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)): the CLI's sign-in is the top-level `lorenzo login`, `logout` and `whoami`, not an `auth` group, so the token login is **`lorenzo login --token`**:

- It needs only the API URL (no issuer or client id): it posts `/device-codes` with `client_name` "lorenzo CLI on <host>", prints the address with the code in it and the plain address with the code to type, and polls `/device-codes/token` every `interval` seconds, **adding five seconds on `slow-down`**, until approved, denied, or `expires_in` passes. It stores the secret in the same `credentials.json` (mode `0600`) as any login, with the token's name (`token_name`); such a login has no issuer or refresh token and is sent as it is. The API URL is remembered like any other login's.
- Every command then uses it (the token order of ADR 0137 is unchanged: `--token-stdin`, `LORENZO_TOKEN`, then the stored login).
- `lorenzo whoami` names it ("personal access token “Laptop”"). `lorenzo logout` deletes the file and says the token still works until it is revoked in the hub (the CLI cannot revoke it: a token manages no tokens, ADR 0268).
- Tested with the fake API in unit tests and, in `tests/e2e`, against the real API and a fake Authgear: the test plays the person in the hub while the CLI polls, then makes a library with the token, revokes it, and sees the next call refused.

**The loot bot** ([ADR 0050](0050-loot-bot-stack-linking-and-isolation.md)) is **not touched**. Its account linking asks for a code from the web today. A later slice could link by pasting nothing: the bot would call `POST /device-codes` with `client_name` "Lorenzo Loot Bot", show the person the code and address in Discord (ephemeral), poll in the background, and store the token it gets in place of today's link, acting through `apps/api` as that user. Its token would show in the same list, named and revocable. Whether the bot should hold a full-as-me token for every linked player, or a narrower credential, is that slice's question and may want the scopes this ADR set aside.

## Consequences

- One approval screen for every future program; the person sees what is asking, names it, and can end it.
- `login --token` works on a machine with no browser: the person approves on another device. It does not depend on the Authgear client registration or the loopback ports.
- Anyone who can read `credentials.json` has the account, as with the refresh token before it; the file mode is the protection. A token with no expiry makes a forgotten file a lasting risk, which the hub's "last used" and Revoke are there for.
- A person deleting their account must do it signed in, not with a token (ADR 0268).
