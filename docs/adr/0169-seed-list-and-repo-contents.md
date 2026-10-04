# 0169 - `lorenzo seed --list` and `lorenzo repo contents`

Status: accepted

Two read-only views, decided with the maintainer on 2026-10-04, after a bare `seed` put a layer into the wrong repository and the process "felt a bit cumbersome and unnecessary, and also a bit intransparent": what the seed contains, and what a repository holds. Built on [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md) (the seed), [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) (its layers as repositories) and [ADR 0159](0159-lorenzo-repo-commands.md) (`lorenzo repo`). It writes nothing, so it needs no new API.

## Context

Both questions had answers, but not from the command line. What `seed` creates is in `builtin.toml` and the README's counts; what a repository holds took a handful of `lorenzo api` calls. After the layers became separate repositories (ADR 0162) the second matters more: whether `core` is complete, whether `dnd5e` is built on it, and whether anything the seed doesn't know about is in there.

## Decision

### `lorenzo seed --list`

```bash
lorenzo seed --list [--layer LAYER ...] [--json]
```

**Prints what the built-in seed makes, per layer, and talks to nobody.** No login, no tenant, no API call, so it works before anything is set up. `--tenant` isn't needed with it, and `--list` together with `--dry-run`, `--yes` or `--allow-play-tenant` is refused rather than quietly ignored.

For each layer it lists the stat groups, the stat definitions (with their group and type), the categories (slug, name, what they sit under, the tags they set), and the recipes, with the seed's version. `--layer` narrows it, as for `seed`. `--json` prints the same as data.

### `lorenzo repo contents`

```bash
lorenzo repo contents --tenant REPOSITORY [--json]
```

**Shows what one repository tenant holds.** It only reads, so it doesn't print the official-instance note a write does ([ADR 0164](0164-the-official-instance-is-the-clis-default.md)). A play tenant is refused, as `repo publish` refuses it.

- **Its state:** published or a draft, and how many tenants it is granted to.
- **What it is built on:** the repositories it has copied (its dependencies, [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)), each with the date it was copied and whether it has published since: the same rows `repo list` gives for any tenant, read for the repository itself.
- **What it holds:** stat groups, stat definitions, and items (categories included), counted. The item count is the API's own total, one request however many there are.
- **How much of each seed layer it holds**, found the way `seed` and `unseed` find things, by slug and name: *complete*, *not there*, or *partly*, saying how many of the layer's stat groups, stat definitions and categories are present.
- **What is beyond the seed:** the stat groups, stat definitions and items the seed doesn't name, as counts.

Exit code 0 when it showed the repository, 1 when it could not.

### What it doesn't do

- **List the items.** Per-category counts and browsing belong to the inventory app; this answers "what is in this repository" in a screenful.
- **Judge a layer as healthy.** "Complete" means every entry the seed names is there. It doesn't check that none was changed, which `seed` never does either.
- **Say what a subscriber would get.** That is `repo copy-plan`.

## Consequences

- The answer to "what is `core`, what is `dnd5e`, and is this tenant either" no longer needs the README or a script, which is what ADR 0162's layers asked of the person running them.
- A seed entry renamed in a repository counts as missing, and its replacement as beyond the seed, because the match is by name. That is the same rule `seed` plans by, so the two views agree with what `seed --dry-run` would do.
- If the seed gains a layer or an entry, both views follow, since they read the same file. A repository seeded by an older version shows as *partly* until `seed` runs again, which is accurate.
