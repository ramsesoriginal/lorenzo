# AGENTS.md

Orientation for AI coding agents (and humans in a hurry) working in this repo.

## What this is

Lorenzo: a multi-tenant REST API plus static frontend(s), Discord bot(s), and mobile app(s) for tabletop/worldbuilding campaign management. See [README.md](README.md) for the pitch, [docs/domain](docs/domain/README.md) for what the system actually models (not technical), and [docs/architecture/overview.md](docs/architecture/overview.md) for the system shape.

**`apps/api` has infrastructure plus the full domain model, a full read/write REST API, and auth** (health/readiness/metrics, DB connectivity; the entity/component core plus tenant/user/membership, campaign/player, character/ownership, campaign GM/orga per [ADR 0012](docs/adr/0012-entity-table.md) onward; Authgear Cloud-backed bearer-token auth per [ADR 0023](docs/adr/0023-authgear-token-verification.md)/[ADR 0027](docs/adr/0027-authgear-cloud-not-self-hosted.md)). **`apps/loot-bot`**, a Discord bot, is built on top of it — account linking, self-service inventory, loot-splitting, GM loot drops with claims, and item awarding, deployed to Cloud Run over Discord's HTTP Interactions Endpoint ([ADR 0050](docs/adr/0050-loot-bot-stack-linking-and-isolation.md) onward). **`apps/inventory-web`** and **`apps/account-hub`**, two static Astro frontends, are built on top of it too ([ADR 0004](docs/adr/0004-static-astro-frontend.md)/[ADR 0071](docs/adr/0071-account-hub-stack-auth-deploy.md)) — GM item catalog/instance management for the former, a user's own account/tenant/campaign/roster surface for the latter — deploying to Cloudflare Pages. Everything else under `apps/` (further web frontends, mobile apps, or bots) is still unbuilt, per [ADR 0007](docs/adr/0007-apps-layout-and-multiplicity.md). The domain model and API were built as a series of small, tested sub-slices (see [RFC 0001](docs/rfcs/0001-core-domain-data-model.md) through [RFC 0012](docs/rfcs/0012-tenant-creation-and-update-api.md)) — keep using that same process for anything new: don't jump ahead to a later sub-slice, and don't add application code speculatively; anything beyond the current sub-slice gets built only once it's explicitly scoped in conversation with the user.

## Map

| Path | Purpose |
| --- | --- |
| `apps/api` | Backend REST API — full domain model, full read/write REST API, Authgear auth, repositories (RFC 0024: tenants other tenants are granted, copy from, and sync with) |
| `apps/loot-bot` | Discord bot — talks to `apps/api`; account linking, inventory, loot-splitting, GM drops/claims |
| `apps/inventory-web` | Static Astro frontend — GM item catalog/instance management, kanban-style container board, LorenzoScript descriptions, tag, information and slug editing, players' notes, handing items over, a public catalog for players; end-to-end tests against the real API (`mise run //apps/inventory-web:test-e2e`, ADR 0114) |
| `apps/account-hub` | Static Astro frontend — a user's own account: profile, notifications, tenant/campaign roster and admin |
| `apps/*` (further) | One directory per deployable app, named by purpose (not type) — next one not yet started |
| `packages/*` | Extracted generic libraries, each its own small, independently versioned package — `packages/brand` (shared brand CSS, ADR 0098), `packages/lorenzoscript` (the LorenzoScript Markdown parser/renderer, RFC 0027), and `packages/lorenzoscript-editor` (its textarea editor) so far |
| `docs/adr` | Why things are the way they are — read before proposing an architectural change |

## Commands

```bash
mise install                                        # toolchains
docker compose -f infra/docker-compose.yml up -d    # Postgres, for apps/api
mise run //apps/api:dev                              # apps/api, with autoreload
mise run lint                                          # fans out to every app (apps/api, apps/loot-bot, apps/inventory-web, apps/account-hub)
mise run test                                           # ditto
mise run check                                          # lint + test - the full pre-PR gate
```

`apps/api`, `apps/loot-bot`, `apps/inventory-web`, and `apps/account-hub` each already own `dev`/`lint`/`test`/`build` tasks in their own `mise.toml` (see [ADR 0007](docs/adr/0007-apps-layout-and-multiplicity.md) and [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md)); CI discovers them automatically, and the next app just needs the same contract.

## Conventions

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/); a commit-msg hook enforces this.
- Merge PRs with a merge commit, never squash/rebase (see [ADR 0005](docs/adr/0005-git-branching-and-merge-strategy.md)) — branch history is kept deliberately.
- No `utils`/misc grab-bags — generic code becomes its own package under `packages/`.
- Any table that stores tenant data needs a `tenant_id` column and an RLS policy with `FORCE ROW LEVEL SECURITY` (see [ADR 0002](docs/adr/0002-multi-tenancy-shared-schema-rls.md); every table since [ADR 0012](docs/adr/0012-entity-table.md) follows this). Never rely on application-level filtering alone. The app's own DB role used to be a superuser, which bypasses RLS unconditionally regardless of policy correctness — fixed by a restricted, non-superuser role ([ADR 0021](docs/adr/0021-restricted-app-role-for-rls-enforcement.md)), rotated and confirmed in production too, not just deployed (see [docs/operations/deployment-setup.md](docs/operations/deployment-setup.md)) — if you're working against an older checkout and not sure whether it has this fix, check for a `lorenzo_app` role and a `migrations_database_url` split in `config.py`.
- Every foreign key between two tenant tables includes `tenant_id` (declare it with `db.same_tenant_fk`, ADR 0117), and every new tenant table goes in one of `repository_access`'s two lists, content a repository can hold or not (ADR 0118). Tests fail on either one missed.
- Formatting/linting is enforced by pre-commit + CI, not by convention.

## Planning: RFC/ADR, Issues, and Milestones

`gh` (GitHub CLI) is available and usable non-interactively — use it. See [ADR 0070](docs/adr/0070-planning-milestones-issues-and-a-deferred-roadmap.md) for the full rationale; this is the day-to-day summary.

Four layers, each with one job — don't blur them:

- **RFC** (`docs/rfcs/`) — a proposal, before it's decided. Becomes one or more ADRs once decided, or gets dropped.
- **ADR** (`docs/adr/`) — the decision itself, with rationale and consequences, recorded once made.
- **Issue/Milestone** (GitHub) — live execution tracking of an *already-decided* RFC/ADR slice. One milestone per ADR (or per RFC, if it's tracked as one slice across several ADRs). An issue references the RFC/ADR number it comes from, its body is a checklist, and it carries no design content of its own — if it needs design debate, it isn't ready to be an issue yet. Close via `Closes #N` in the PR description (works fine under this repo's merge-commit-only rule — the keyword lives in the PR body, not the commit).
- **`ROADMAP.md`** — deliberately doesn't exist yet. Don't add one speculatively; see ADR 0070 for the named trigger and the exact (link-only, no independent prose) shape it gets built in when that trigger fires.

At the start of a session, `gh issue list --state open --milestone <N>` (or unscoped) is the live "what's actually in flight" query — prefer it over re-deriving status from memory or from `docs/architecture/overview.md`'s roadmap section, which is an append-only historical chronicle, not a live status board.

**Claim RFC/ADR numbers early, to avoid collisions — but never merge that PR yourself.** This project's ADR numbering has already collided several times across long-lived parallel branches (see the renumbering notes on ADR 0050/0054, and the Addendum on [ADR 0070](docs/adr/0070-planning-milestones-issues-and-a-deferred-roadmap.md) for a fourth, live example). The exact procedure, precisely because "merge it early" was ambiguous enough once to get misread as "merge the PR yourself":

- **One RFC/ADR sub-branch per feature, not per document.** Create it once, off the feature branch, and reuse it for every RFC/ADR that comes up while working that feature — including ones discovered mid-implementation. Don't spin up a new sub-branch for those; keep using this one.
- **Per RFC/ADR**: check the current highest number on `main` *and* any open PRs (`gh pr list`) first. Write it, commit it on the sub-branch, merge (`git merge`, not rebase) the sub-branch into the feature branch so implementation can build on it immediately, push the sub-branch to origin, and open a PR from the sub-branch into `main` if this feature doesn't already have one for its docs — otherwise the new commit just lands on the existing PR.
- **Push and open/update that PR. Do not merge it.** Merging into `main` is left for review, exactly like any other PR into `main` — the early branch + open PR already gives the collision-avoidance and cross-branch visibility benefit; it doesn't require an autonomous merge into the shared branch to do that.
- Open or expand the tracking Issue/Milestone at the same time — not forced 1:1 with each document. Expand an existing Milestone, or add another Issue under one, where that actually fits better than minting a new one.
- If two branches still land on the same number despite this, renumber the later one with a documented history note, same as the existing precedent.

## Worktrees

Bigger changes — a big feature, a full-app refactor, a new app, or anything the user explicitly asks for by name — get their own [git worktree](https://git-scm.com/docs/git-worktree) rather than switching branches in place, so more than one line of work can sit checked out at once. Small changes (a doc fix, a one-line bugfix, a chore like this one) stay in the main checkout as before.

- Worktrees live as siblings of this checkout, one directory per branch, path mirroring the branch name exactly: `../lorenzo-worktrees/<branch>` (e.g. `../lorenzo-worktrees/feat/loot-bot`, `../lorenzo-worktrees/docs/brand-mascot`) — the convention already in use (`git worktree list` shows the current ones).
- If the target branch already has a worktree, use it — `cd` there and work from it, don't create a second one and don't work from the main checkout instead.
- If it doesn't yet, create one the same way: `git worktree add ../lorenzo-worktrees/<branch> <branch>` for a branch that already exists, or `git worktree add ../lorenzo-worktrees/<branch> -b <branch>` (off `main`) for a new one.
- Splitting a big feature across several parallel (sub)agents: each one gets its own sub-branch off the *feature* branch, not off `main`. **Not a `/`-nested name** (`<feature-branch>/<sub-slug>`) — git refuses that outright once `<feature-branch>` already exists as a ref (`refs/heads/feat/x` can't also be a directory containing `refs/heads/feat/x/y`), confirmed the hard way. Use a hyphen instead: `<feature-branch>-<sub-slug>` (e.g. `feat/rest-api-surface-campaign-crud`). Its worktree then follows the *same* top-level rule as any other branch — path mirrors the branch name exactly, `../lorenzo-worktrees/<feature-branch>-<sub-slug>` — no special nesting case needed; a literal "one level deeper" path was tried and fails too, since it would sit inside the parent branch's own worktree directory, which is already that branch's full checkout root, not a container other worktrees can live inside. Each agent does its slice of work there, then merges back into the feature branch (a real merge commit, same convention as merging into `main`) once done — never straight into `main`. Remove the sub-worktree after merging (`git worktree remove ../lorenzo-worktrees/<feature-branch>-<sub-slug>`); the branch itself can stay, same as any other merged branch.

## Before making a change

1. Check [docs/adr](docs/adr/README.md) — is this decision already made, and why?
2. If this is about adding a new app: read [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md) and confirm scope with the user before writing code.
3. Prefer the smallest vertical slice that's actually tested end to end over a broad partial implementation — but only once asked to build, not while still preparing structure.
4. Decide whether this needs its own [worktree](#worktrees) before creating or switching branches.
