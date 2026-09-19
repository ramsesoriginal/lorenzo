# 0070 - Planning: GitHub Milestones/Issues alongside RFC/ADR, early RFC/ADR merges, and a deferred roadmap

Status: accepted

## Context

Until now, forward-looking planning for this project happened entirely off the record: RFC/ADR for design decisions, and otherwise the maintainer's own memory, creativity, and motivation. No GitHub Issues were used. A single symbolic GitHub Milestone (#1) existed briefly and has since been deleted - the [README.md](../../README.md)'s own link to it is dead (`404`), which nobody noticed until this ADR's own research turned it up.

The one attempt at a forward-looking artifact this project actually had - the "## Roadmap" section in [docs/architecture/overview.md](../architecture/overview.md) - had rotted: a stale "only `apps/api` exists so far" claim contradicting its own table two lines down, a dead milestone link (twice), and a buried, easy-to-miss "remaining, not yet built" clause tangled inside a wall of historical prose. In the same documentation-audit session that found this, several other hand-maintained narrative docs in this repo were independently found stale too - the root `CHANGELOG.md`, claims in this project's own `AGENTS.md`, an ER diagram missing six tables, a deployment doc with a six-year-stale migration count. This isn't one unlucky doc; it's a pattern: **hand-maintained prose that duplicates state nobody's job it is to keep current, reliably drifts in this repo.**

Separately, this project's own ADR numbering has already collided twice - ADR 0050 and ADR 0054 both had to be renumbered at merge time because a long-lived parallel branch (`feat/loot-bot`) and `main` had each independently claimed the same number range while both were in flight, undiscovered until merge (see the renumbering notes on both entries in [docs/adr/README.md](README.md)). While researching this ADR, a live third *and* fourth example turned up at once: two different open branches - `feat/loot-bot-inventory-and-gm-tools` and `feat/inventory-web-app` (PR [#72](https://github.com/ramsesoriginal/lorenzo/pull/72)) - had each independently claimed ADR numbers 0068 and 0069 for overlapping loot-bot inventory/GM-toolkit work. The first landed on `main` for real as this ADR was being written (see [ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)/[0069](0069-item-instance-container-flag-group-writes-bulk-container-move.md)); PR #72's own copies of those numbers are now stale duplicates that will need their own renumbering pass at merge time, per the existing precedent. This ADR is numbered **0070**, past both claims, specifically to avoid adding a fifth collision on top - a number reserved by *checking first*, not by luck.

This project is public, AGPL-3.0, and explicitly aims at outside contributors eventually (issue templates and a Discussions link already exist in `.github/`); it isn't there yet, but "not yet" needs an honest trigger, not silent deferral forever. The maintainer works heavily with AI coding agents (Claude Code) that have no memory across sessions beyond what's written in the repo, and now have `gh` (GitHub CLI) available non-interactively.

This decision followed a structured, adversarial debate among four independently-researched positions (dedicated `ROADMAP.md`; lean fully into GitHub Issues/Milestones; add nothing and fix the existing prose; a full three-artifact hybrid). All four converged, under cross-examination, on the same conclusion: **an artifact only resists this repo's demonstrated rot if its state is structural (flips for free as a side effect of merging), not authored** - which is why the dedicated-roadmap and full-hybrid positions each retreated from their own centerpiece once pressed on enforcement.

## Decision

**1. Adopt GitHub Milestones + Issues as the live execution-tracking layer, alongside RFC/ADR, not instead of it.**

- **RFC** = pre-decision proposal (unchanged - "becomes one or more ADRs once decided, or gets dropped").
- **ADR** = the decision, with rationale and consequences, recorded once made (unchanged).
- **Issue** = one already-decided, already-scoped execution unit pulled from an accepted RFC/ADR. Title references the RFC/ADR number; body is a checklist; no design debate lives there - if it needs design debate, it isn't ready to be an issue yet.
- **Milestone** = one per ADR (or per RFC, if that RFC's own implementation is tracked as a single slice spanning several ADRs). A milestone closing because its issues closed is a free, accurate "is this actually done" signal - nobody has to remember to update it.
- **Labels**, kept deliberately small since this is a near-solo repo, not a taxonomy exercise: `app:api`, `app:loot-bot`, `app:inventory-web` (one per `apps/*` directory, added as each app is scaffolded - see [ADR 0007](0007-apps-layout-and-multiplicity.md)); `tracking` (marks an issue as RFC/ADR-execution tracking, distinct from an organically-filed bug/feature request); `status:blocked`; `triage` and `chore` (filling two real gaps: `triage` was already referenced by the existing issue-form templates but never actually created; `chore` has no existing equivalent among GitHub's default labels, unlike `bug`/`enhancement`/`documentation`, which this repo already has and which nothing here duplicates).
- **Auto-closing**: `Closes #N` in the PR description. This works unmodified under this repo's merge-commit-only rule ([ADR 0005](0005-git-branching-and-merge-strategy.md)) - the closing keyword lives in the PR body, not the commit, so it's untouched by the squash/rebase question entirely.
- **`gh` in day-to-day use**: an agent's session-start backlog query is `gh issue list --state open --milestone <N>` (or unscoped, for "what's open at all") - a live, structural answer to "what's in flight," instead of re-deriving it from memory or dense ADR prose.

**2. RFC/ADR branch-and-merge-early convention, to shrink the collision window this project has already hit twice.**

When starting a new RFC or ADR, put it on its own small branch (or as an early, separable commit within a larger feature branch per the existing [worktree convention](../../AGENTS.md#worktrees)), and merge *that document* - number, title, Context, Decision - into `main` (or the parent feature branch, if this is sub-work within one) as soon as the decision itself is actually settled, before the rest of the implementation is done. Open the tracking Issue/Milestone at the same moment. The two together give layered visibility: the issue is visible instantly, repo-wide, to any other branch or agent that queries it (no fetch/merge needed); the merged ADR/RFC file is the durable, canonical record once it lands. **(This paragraph's "merge into `main`" turned out to be ambiguous about who does that merge - see the Addendum below for the corrected, unambiguous version.)**

- This applies straightforwardly to RFCs, which are already meant to exist as a public, pre-implementation proposal.
- For ADRs specifically, one adjustment to existing practice: this project's ADRs have generally been written to describe what was actually built, with a `Consequences` section referencing real file/test names. That's still the right final state, but nothing here blocks writing and merging an ADR's `Context`/`Decision` as soon as the decision is genuinely final, with `Consequences` filled in more precisely in a small follow-up amendment to the same file once the implementation actually ships. That's permission for what already sometimes happens under time pressure, made explicit rather than ad hoc.
- Early merging shrinks the collision window; it doesn't eliminate the race. If two branches still land on the same number, the existing recovery path - renumber the later one, with a documented history note pointing at the collision (the precedent already set by ADR 0050 and 0054) - remains exactly as it was.

**3. Defer `ROADMAP.md`, but name the trigger and pre-commit to its shape.**

No dedicated roadmap file is added now. The trigger to add one: the first time an outside Discussion or Issue asks "what's planned" and the honest answer requires reading raw ADRs. Deciding the shape in advance, rather than re-litigating it in the moment, is what keeps "not yet" from silently becoming "never":

- **Now/Next/Later** format, capped, conceptual (themes, not tasks - tasks are what Issues are for).
- Every line is a link to a Milestone, an open RFC, or nothing else - **no independent prose is permitted**, ever, in this file.
- A trivial enforcement check lands in the same PR that creates the file (e.g. a script or markdownlint rule failing any line without a `docs/adr/`, `docs/rfcs/`, or issue/milestone-shaped link) - specifically because this repo has now demonstrated, more than once, that an unenforced "links only" convention degrades exactly like free prose does, just on a longer fuse.

**4. Fix `docs/architecture/overview.md`'s Roadmap section now, regardless of the above.**

Done as part of this same change: split the append-only historical chronicle (kept, it's accurate and ADR-sourced) from the one genuinely forward-looking clause (trimmed, reworded to make clear it's a list of *open design questions*, not a task list, and explicitly not tracked as issues until something actually picks them up); removed the two dead `github milestone #1` links; added an explicit rule at the top of the section - historical facts only, append-only, live status belongs in Issues/Milestones instead.

## Not in scope

- Actually creating `ROADMAP.md` - deferred per decision 3 above, not rejected.
- GitHub Projects/kanban boards - Milestones + Issues are enough at this scale; revisit only if Milestones' flat structure genuinely becomes limiting.
- Retroactively opening issues for already-shipped work - per the project's own RFC/ADR audit, everything through ADR 0067 is already `accepted` (built) or `superseded`; there is nothing there to backfill.
- Turning the open design questions listed in `overview.md` (RFC 0001's redaction question, per-tier information authorization, cross-tenant repositories) into issues - none of them is decided or scoped yet, and this project's own standing rule ("anything beyond the current sub-slice gets built only once it's explicitly scoped in conversation with the user," [AGENTS.md](../../AGENTS.md)) applies to planning artifacts exactly as it applies to code. An issue is for tracking already-decided work, not for manufacturing a backlog out of open questions nobody's picked up.
- A dedicated ADR amending [ADR 0005](0005-git-branching-and-merge-strategy.md)'s branching rules wholesale - the early-merge convention in decision 2 is additive to it, not a replacement.

## Consequences

- `docs/architecture/overview.md`'s Roadmap section is fixed (split chronicle/open-questions, dead links removed, discipline rule stated).
- [AGENTS.md](../../AGENTS.md) gains a section explaining the RFC/ADR/Issue/Milestone model, that `gh` is available, and the branch-and-merge-early convention.
- [docs/adr/README.md](README.md) gains a short note pointing at this convention, next to the existing renumbering-precedent notes.
- New labels (`app:api`, `app:loot-bot`, `app:inventory-web`, `tracking`, `status:blocked`, `triage`, `chore`) and a new issue template for RFC/ADR-linked tracking issues are added.
- A Milestone + Issue are created now for the one real piece of in-flight work this ADR's own research turned up: PR #72 (`apps/inventory-web`, the first web frontend, plus its own now-stale copies of ADR 0068/0069 that still need renumbering at merge time) - itself a demonstration of the convention this ADR adopts.
- `README.md`'s dead milestone-#1 link is removed.
- Future sessions (human or agent) get a cheap, structural answer to "what's in flight" via `gh issue list`/`gh api .../milestones`, instead of re-deriving it from memory or from prose that has already proven it won't stay honest on its own.

## Addendum (2026-09-18): the sub-branch is reused per feature, and its PR into `main` is never self-merged

The first real feature built under this convention (`apps/account-hub`: [RFC 0013](../rfcs/0013-account-hub-app.md), [ADR 0071](0071-account-hub-stack-auth-deploy.md)) surfaced two things decision 2 above didn't actually say, even though it was written as if it had:

1. An agent correctly created a dedicated branch, wrote the RFC, pushed it, and opened a PR into `main` for it - then did the same for the ADR on a **second, separate** branch. Decision 2 says "put it on its own small branch" per RFC/ADR, read literally as one branch per document. What's actually wanted is one branch **per feature**, reused for every RFC/ADR that comes up while working it (including ones discovered mid-implementation) - not a fresh branch each time.
2. The agent then **merged both PRs into `main` itself.** Decision 2 says to "merge that document... into `main`" without ever saying *who* performs that merge - an ambiguity that reads as authorization once an agent is already used to being trusted with `git merge`/`git push`. It isn't: merging into `main` is a shared-branch action that stays under normal review, exactly like any other PR into `main` (see this repo's own top-level operating rules on actions with blast radius beyond the local branch). The early-branch-and-open-PR already delivers the collision-avoidance and visibility this decision wanted; an autonomous merge into `main` was never required to get that.

Corrected procedure, replacing decision 2's operational detail (the *why* - structural state over authored prose - is unchanged):

- One RFC/ADR sub-branch **per feature**, created once off the feature branch, reused for every RFC/ADR that comes up while working that feature.
- Per RFC/ADR: check the current highest number on `main` and open PRs, write it, commit on the sub-branch, merge (`git merge`, not rebase) the sub-branch into the feature branch so implementation can build on it immediately, push the sub-branch, and open a PR from it into `main` if this feature doesn't already have one for its docs - otherwise the new commit just lands on the existing PR.
- **Push and open/update that PR. Do not merge it.** That step is left for review, full stop.
- Milestone/Issue creation stays not-forced-1:1, as decision 1 already said - this addendum doesn't change that part.

[AGENTS.md](../../AGENTS.md)'s Planning section has been updated to state this unambiguously rather than leaving it to be inferred.
