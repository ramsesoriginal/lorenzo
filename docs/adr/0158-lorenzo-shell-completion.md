# 0158 - Shell completion

Status: accepted

Follow-up to [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md). Part of the set decided together on 2026-10-03 ([ADR 0153](0153-lorenzo-version.md)).

## Context

The CLI has about a dozen commands with long, similar options (`--allow-play-tenant`, `--public-catalog`, `--accept-moves`), and ADR 0137's app was created with `add_completion=False`, so none of it completes. Typer ships completion for bash, zsh, fish and PowerShell; it was switched off, not missing.

## Decision

Turn it on. `lorenzo --install-completion` and `lorenzo --show-completion` appear in `lorenzo --help`, as Typer provides them.

- **Installing is the person's own act.** Nothing edits a shell's startup file unless `--install-completion` is run. `--show-completion` prints the script instead, for someone who keeps their own dotfiles.
- **It completes commands, subcommands and options**, and the fixed choices (`--kind repository|play`, `--layer`).
- **The README says how**, in the section on installing.

## Not in scope

- **Completing tenant slugs, repositories or pack names.** That would call the API, with a token, on every Tab, from inside a shell. It might be wanted later, but it is a different feature with its own timeouts and failure modes, and a slow completion is worse than none.
- **Windows.** Native Windows isn't a supported target ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)); PowerShell completion comes with Typer but isn't tested here.

## Consequences

- Long option names are a Tab away.
- `lorenzo --help` gains two lines.
