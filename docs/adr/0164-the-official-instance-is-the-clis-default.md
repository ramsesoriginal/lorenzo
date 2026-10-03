# 0164 - The official instance is the CLI's default

Status: accepted

Supersedes the "no default" clauses of [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md) and [ADR 0157](0157-lorenzo-remembers-the-api-url-issuer-and-client-id.md). Decided with the maintainer on 2026-10-03.

## Context

ADR 0137 fixed that the CLI has **no default API URL**, "so a token never goes to a host nobody chose", and ADR 0157 kept that rule when it let `login` remember what a person typed. The reason was sound while there was no deployment to point at. Now there is one: an API on Cloud Run, an Authgear project at `lorenzo.authgear.cloud`, and a public Authgear client registered for the CLI (a Single Page Application, no secret, redirect URIs only on `127.0.0.1`).

The result of the rule was that a stranger had to be handed three values (an address, an issuer, a client id) before `lorenzo login` could do anything, and had to know that they belonged together. The maintainer asked for the right values to be the default, and asked what that risks. The values themselves are public. The risks are about where a token goes and what a default makes easy:

1. **Production becomes the path of least resistance.** An unset address used to stop the command. With a default, a script or a development run that forgot to point at a local API would write to production, with a real token.
2. **Mixed trust.** The official issuer with someone's own API (or the reverse) would send a bearer token to the wrong party, who could replay it until it expires.
3. **Hard-coded addresses age.** The Cloud Run address and Authgear's free-tier subdomain change if the project moves to a custom domain, a new Authgear project or a paid plan.
4. **Forks and self-hosters.** The project is AGPL, so a fork's CLI would talk to the official API until it changes the defaults.

## Decision

**The three values, together, are the CLI's default.** They live in one module, `lorenzo_cli/defaults.py`: the official API address, the Authgear issuer, and the client id. They are public values, not secrets, as the web apps' client ids already are.

### As a set, never one at a time

This is what answers the second risk. A default applies **only when nothing other than the official values has been named**:

- Each setting still comes from a flag, then the environment, then the remembered file ([ADR 0157](0157-lorenzo-remembers-the-api-url-issuer-and-client-id.md)). Anything named there wins.
- If any of the three is named and **differs from the official one**, none of the others is filled in from the defaults. `--api-url http://localhost:8000` points at a local API and nothing else: no official issuer is assumed for it, so `lorenzo login` asks for the issuer and client id of the Authgear project that API trusts, and `LORENZO_TOKEN` (which needs no issuer) just works.
- A value that equals the official one counts as not having named anything, so pasting the official address, or the official values together, behaves as if nothing was named. A trailing slash makes no difference.
- The error for a missing address says so: the official Lorenzo is the default only when none of the three has been named otherwise.

### Remember only what differs

`login` remembers what it used ([ADR 0157](0157-lorenzo-remembers-the-api-url-issuer-and-client-id.md)), but **never what came from the defaults**: a remembered copy of the official values would outlive them, and keep sending people to an address that has moved. When a login ends up using exactly the official set, even if it was typed, `login` **forgets** the remembered file instead of writing one, and says so if there was one, so an older self-hosted address doesn't linger after someone returns to the official instance.

### Seeing where it goes

This answers the first risk, without a prompt on every command:

- **`login` says where it is signing in** and for which API, before it opens anything.
- **`whoami`** shows the API, marked `(the default)` when it is.
- **A command that writes says so**, once, on stderr, when the official default is in use: `Using the official Lorenzo at <address>.` That covers `tenant create`, `seed` (not `--dry-run`), `apply`, `pack give` (not `--dry-run`), `repo` commands that change something, and `lorenzo api` with anything but `GET`. Reads stay quiet, and so does everything once an address has been named. Nothing is asked: it is a line to read, not a gate.
- Writing against a local or staging API stays a matter of naming it, by flag, environment or file, as it was; and `LORENZO_API_URL` in a development shell is the one habit this asks for.

### When the defaults change

They are one module and a release. The third risk is real and accepted: if the address or the Authgear project moves, `defaults.py` changes, the CLI is released, and people upgrade (`uv tool upgrade lorenzo-cli`). Someone whose environment or file names the old values keeps them, which is the point of naming them. A custom domain for the API before 1.0 would make the address the least likely of the three to move; the issuer stays on Authgear's domain on the free tier. `docs/operations/deployment-setup.md` names `defaults.py` as the place to change, with the Authgear section.

## Not in scope

- **A prompt or `--yes`-style gate before writing to the default.** A line to read was chosen over a step to click through; an environment that wants the gate can unset the defaults by naming another address.
- **Baking in anything else.** The tenant, a token, or the Cloud Run revision are not defaults.
- **Per-fork defaults at build time.** A fork changes one module.
- **A profile mechanism** (`--profile staging`). The environment and the remembered file cover it until it doesn't.

## Consequences

- A newcomer's first run is `lorenzo login`, then `lorenzo whoami`. "Before you start" shrinks to the account and, for creating tenants, the `tenant-creator` role.
- A self-hoster names all three once (flags, environment, or `login`, which remembers them), exactly as ADR 0157 described, and never touches the official instance by omission: naming any of them turns the defaults off for the rest.
- ADR 0137's guarantee is weaker and different: not "a token never goes to a host nobody chose", but "never to a host the person didn't either name or accept as the official default, and never in a mixed pair". The stored login's own issuer and client id are unchanged.
- The six unit tests that assumed "no address refuses" were rewritten around the set rule (a differing issuer stands in for "something else was named"); the end-to-end tests already name every address.
