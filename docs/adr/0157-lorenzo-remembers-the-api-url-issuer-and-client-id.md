# 0157 - `lorenzo login` remembers the API URL, the issuer and the client id

Status: accepted

Amends [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md). Part of the set decided together on 2026-10-03 ([ADR 0153](0153-lorenzo-version.md)).

## Context

Using the CLI against a real deployment takes three settings, all of them the same on every run: the API's address (`LORENZO_API_URL`), and for `login` the Authgear issuer and client id (`LORENZO_AUTHGEAR_ISSUER`, `LORENZO_AUTHGEAR_CLIENT_ID`). Today all three live in the environment, so a person who installs the tool has to export three variables in every shell before anything works, and an unset one fails with a message about a variable.

The stored login ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)) already holds the issuer and the client id, because a refresh needs them. But it holds them only with the tokens, and `logout` deletes the file, so the next `login` starts from nothing again. It doesn't hold the API URL at all.

ADR 0137 also fixed that **there is no default API URL**, so that a token never goes to a host nobody named. That rule stands: nothing here makes a default. What changes is that an address someone typed once can be remembered.

## Decision

### A settings file

`$XDG_CONFIG_HOME/lorenzo/config.toml` (`~/.config/lorenzo/config.toml` without `XDG_CONFIG_HOME`), beside `credentials.json`:

```toml
api_url = "https://api.example"
issuer = "https://example.authgear.cloud"
client_id = "abc123"
```

- **It holds nothing secret**, so unlike the credentials file it is an ordinary file. It is written whole and replaced atomically, in a directory created `0700` as the credentials file already does.
- **Unknown keys are ignored** and a file that isn't valid TOML is treated as absent, with a warning, never a crash: the same forgiving read the credentials file has.

### Who writes it

`lorenzo login` does, after it succeeds, with the three values it just used. They come from, in this order:

1. **a flag**: `--api-url` (already a global option), and new `--issuer` and `--client-id` on `login`;
2. **the environment**: the three variables above;
3. **the file itself**, from an earlier login.

So the first login is `lorenzo login --api-url https://api.example --issuer https://example.authgear.cloud --client-id abc123`, and from then on `lorenzo login` alone works, as does every command that needs the API address.

- **Only what was resolved is saved.** A login that never learned an API URL saves no API URL.
- **Other commands read the file and never write it.** A one-off `--api-url` on `lorenzo plan` doesn't change what is remembered.
- **`logout` forgets the tokens and keeps the settings.** Signing out is not forgetting where you sign in. Deleting `config.toml` forgets them; the README says so.
- **Precedence everywhere is flag, then environment, then file**, so a script's environment still wins over a person's saved settings.
- **A token from `LORENZO_TOKEN` or `--token-stdin` still needs no login**, and still finds the API URL in the file if no variable names one.

### Messages

A missing API URL now says how to fix it for good: set `LORENZO_API_URL` or pass `--api-url` for a run, or `lorenzo login --api-url …` to remember it. A `login` missing an issuer or client id names the flag as well as the variable.

## Not in scope

- **A default for any of the three**, for the official instance or any other. ADR 0137's rule about naming a host stands.
- **A `lorenzo config` command** to set or show values without logging in. `whoami` ([ADR 0155](0155-lorenzo-whoami.md)) shows the API address in use, and the file is three lines. If a person on `LORENZO_TOKEN` alone asks to remember an address, that is the case for it.
- **Several profiles**, for a development and a production API side by side. The environment overrides cover that today.

## Consequences

- After one login, the CLI works from any shell with nothing exported.
- A saved API URL is a saved choice of where tokens go. It is one the person typed, but it will keep being used until they change it, which is why the file is plain, short, and named in the README.
- The stored login's own issuer and client id stay what refresh uses. The settings file is only where the next login starts.
