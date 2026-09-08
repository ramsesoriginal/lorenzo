# 0003 - Polyglot monorepo tooling

Status: accepted

## Context

This monorepo will eventually hold Python, TypeScript, and likely Kotlin and/or Ruby side by side, across possibly many apps of the same type (see [ADR 0007](0007-apps-layout-and-multiplicity.md)). JS-first monorepo tools (Nx, Turborepo) assume a JS root and treat other languages as an afterthought.

## Decision

- **mise** for toolchain pinning and cross-language task running — except Python's own version, which **uv** controls directly via each Python app's `.python-version` file. Every real app owns its own `mise.toml` defining, at minimum, `dev`/`lint`/`test`/`build` tasks; the root aggregates them via mise's monorepo task feature (wired now that `apps/api` exists — root `mise.toml`'s `[monorepo].config_roots`). CI discovers apps the same way (`ci.yml`'s `discover` job), rather than hardcoding app names.
- **uv** workspace for Python packages/apps — introduced once the first Python app or shared Python package actually needs to share a lockfile with another, not before. `apps/api` is a standalone uv project; a root-level workspace with nothing in it caused real rework the first time this was tried (the lockfile's location depends on workspace membership, and that's not worth fixing twice before there's anything to share).
- **pnpm** workspace for JS/TS packages/apps — declared now (`pnpm-workspace.yaml`, matching zero JS/TS apps today) since an empty glob is harmless, unlike uv's lockfile-placement behavior.
- **release-please** (manifest mode) for independent per-package SemVer, Keep a Changelog-style changelogs, and GitHub Releases — `apps/api` is registered (`release-type: python`) and has been tagging real releases since it started landing on `main`; a package entry gets added as each further app/package is registered. See [docs/operations/releasing.md](../operations/releasing.md) for how it actually behaves in practice, including the rough edges found running it for real.
- **pre-commit** as the one cross-language hook runner. Language-specific hooks are added alongside the first app that needs them — ruff is wired now, scoped to `apps/api/`.

No language gets a second-class task-running experience; adding a Kotlin or Ruby app later means adding a `mise.toml` in that app plus a release-please package entry, not adopting a different toolchain.

## Consequences

Contributors need `mise` installed as the one prerequisite; everything else (node, uv, pnpm-via-corepack, and Python via uv) is then pinned and installed per-project as those projects come into existence. CI uses the same `mise.toml`/`.python-version` files so local and CI toolchains can't drift. Concretely: `uv sync` respects `requires-python` in `pyproject.toml` plus `.python-version`, and will fetch a matching interpreter itself rather than relying on whatever Python happens to be on `PATH` — mise deliberately doesn't list `python` under `[tools]`, to avoid two systems both trying to own the same version.
