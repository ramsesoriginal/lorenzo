# Labels, milestones, assignees, and links

Every issue and pull request in this repo carries the same small set of metadata, so "what touches `apps/api`", "what belongs to RFC 0031", or "what is still open on the CLI" is one filter away. This guide is the day-to-day rule set; the planning model behind it (RFC → ADR → Issue/Milestone) is [ADR 0070](../adr/0070-planning-milestones-issues-and-a-deferred-roadmap.md), and its label list is superseded by the tables below (see that ADR's addendum).

**The rule: nothing is opened without labels, an assignee, and (where one exists) a milestone.** Do it when you create the issue or PR, not as a cleanup pass afterwards. It was cleaned up once, in bulk, on 2026-09-29; keep it that way.

## Getting at GitHub

Use whichever of these works in your environment, in this order:

1. **`gh` on `PATH`.** Usable non-interactively.
2. **`gh` inside WSL** (`wsl gh ...`) when the host shell doesn't have it. WSL re-parses its arguments, so never pass bodies, titles with backticks, or JSON on the command line: use `--body-file -` or `--input -` and feed stdin. Run it from the main checkout, not from a worktree (it fails there). Query strings containing `&` or `?` break too: use `-X GET -f key=value` instead of a `?a=b&c=d` URL.
3. **The GitHub MCP server**, if it is connected and authorised in your session.

## Labels

Labels come in four families. Pick from each family where it applies; an item usually has one type label and one or more scope labels.

### Type: what kind of change

| Label | Use for | Conventional-commit prefix |
| --- | --- | --- |
| `enhancement` | A new capability or user-facing improvement | `feat` |
| `bug` | Something that was broken | `fix` |
| `documentation` | Docs-only change (`docs/`, READMEs, RFCs, ADRs) | `docs` |
| `chore` | Maintenance, refactors, no user-facing behaviour change | `chore`, `refactor`, `perf` |
| `ci` | GitHub Actions and repo automation | `ci`, `chore(ci)` |
| `test` | Tests and test infrastructure | `test` |
| `breaking-change` | Incompatible API or CLI change | any type with `!` or a `BREAKING CHANGE:` footer |
| `infra` | Deployment, hosting, local infrastructure (Cloud Run, Neon, Cloudflare, Docker Compose) | usually with `fix`/`chore`/`docs` |
| `release` | A release-please release PR | `chore: release ...` |
| `rfc` | A PR that proposes or amends an RFC | `docs(rfc)` |
| `adr` | A PR that records or amends an ADR | `docs(adr)` |

`enhancement` (not `feature`) stays because the `feature_request` issue template references it.

### Scope: where the change lands

One label per directory that ships something, named after it. A change touching several gets several.

- `app:<name>` for each `apps/<name>`: `app:api`, `app:loot-bot`, `app:inventory-web`, `app:account-hub`, `app:cli`, `app:brand`, `app:bench`.
- `pkg:<name>` for each `packages/<name>`: `pkg:api-client`, `pkg:brand`, `pkg:lorenzoscript`, `pkg:lorenzoscript-editor`.

How to choose them:

- Use the scope in the PR title (`feat(loot-bot): ...`) first, then the directories the diff actually changes.
- Ignore generated files: a `feat(api)` PR that only regenerates `lorenzo-schema.d.ts` in the other apps is `app:api`, not all of them.
- Docs PRs carry the scope of what the document is *about* (an ADR about account-hub is `app:account-hub`).
- **A new app or package gets its label in the same PR that scaffolds it**, see below.

### Process

| Label | Meaning |
| --- | --- |
| `tracking` | An issue that tracks one already-decided RFC/ADR slice (all issues from the tracking template) |
| `triage` | Needs a decision on scope or priority |
| `status:blocked` | Waiting on something else |
| `duplicate`, `invalid`, `wontfix`, `question` | The GitHub defaults, used when closing or clarifying |

### Owned by bots

`dependencies`, `github_actions`, `python:uv`, `docker`, `javascript` (Dependabot) and `autorelease: pending` / `autorelease: tagged` (release-please) are created and applied by the bots. Don't rename or delete them; renaming makes the bot recreate the original. Do add the scope label (`app:loot-bot` for a loot-bot bump) and the assignee when you touch one.

## Assignee

Assign yourself (`--assignee @me`) on every issue and PR you open, and on bot PRs you handle. With more people on the project, assign whoever is actually responsible.

## Milestones

- **One milestone per RFC or ADR slice**, titled `RFC NNNN - name` or `ADR NNNN - name` (ranges like `ADR 0111/0112 - ...` are fine when they ship together). The description links to the document on `main`.
- **Create the milestone when the RFC/ADR is accepted**, alongside its tracking issues. Not before: an undecided RFC does not get one (the empty `RFC 0018` milestone is a deliberate exception, kept as a placeholder).
- **Every tracking issue and every PR that implements or documents that slice goes into it**: the docs PR that records the ADR, the implementation PRs, the follow-up fixes and the doc catch-up. A PR can hold only one milestone; when it spans two, use the one it closes an issue of.
- **Close a milestone when nothing in it is open.** A milestone whose issues are all closed but which is still open is the bug this catches. Leave it open only when the RFC is deliberately partly implemented (RFC 0015/0016 do).
- **No milestone** is correct for Dependabot bumps, release-please PRs, "merge `main` into a branch" PRs, general documentation upkeep, and PRs for RFCs that are still proposals.

## Linking

- An issue that a PR finishes is closed by `Closes #N` in the **PR description** (not the commit). Put one line per issue: `Closes #12`, `Closes #13`.
- A PR that only relates to something says `Related to #N` or `Follows #N`; don't use a closing keyword for that.
- A tracking issue names its RFC/ADR in the title (`ADR 0084: ...`) and links it in the body; the PR links the ADR in its description.
- Stacked PRs (each based on the one below) name the one they depend on in the description. Retarget the base when the one below merges.
- Sub-PRs merged into a feature branch and the feature PR into `main` both carry the same milestone and scope labels; the `Closes #N` lines go on the PR that lands on `main`.

## Doing it from the command line

Open with everything at once:

```bash
gh pr create --base main --title "feat(loot-bot): ..." --body-file - \
  --label enhancement --label app:loot-bot \
  --assignee @me --milestone "RFC 0021 - loot-bot player toolkit (ADR 0088-0097)" < body.md

gh issue create --title "ADR 0140: ..." --body-file - \
  --label tracking --label app:api --assignee @me --milestone "ADR 0140 - ..." < body.md
```

Fix an existing one:

```bash
gh pr edit 123 --add-label bug --add-label app:api --add-assignee @me --milestone "ADR 0099 - player-facing change feed"
gh issue edit 45 --milestone "ADR 0099 - player-facing change feed"
```

Create a milestone (the description carries the link to the design):

```bash
gh api -X POST repos/ramsesoriginal/lorenzo/milestones --input - <<'EOF'
{"title": "ADR 0140 - name", "description": "Execution tracking for ADR 0140. Design lives in https://github.com/ramsesoriginal/lorenzo/blob/main/docs/adr/0140-....md, not here."}
EOF
```

Close it when its last issue closes (`gh api -X PATCH repos/ramsesoriginal/lorenzo/milestones/<N> -f state=closed`).

Audit: what is missing?

```bash
gh pr list --state all --limit 500 --json number,title,labels,milestone,assignees \
  --jq '.[] | select(.assignees == [] or .labels == []) | "#\(.number) \(.title)"'
gh issue list --state all --limit 500 --json number,title,labels,milestone,assignees \
  --jq '.[] | select(.milestone == null or .assignees == []) | "#\(.number) \(.title)"'
```

## When you add an app or a package

In the same PR that scaffolds it:

1. Create its label: `app:<name>` (colour and a `apps/<name>` description) or `pkg:<name>`.
2. Add it to the table in this guide.
3. Apply it to the scaffolding PR itself and to its tracking issues.

```bash
gh label create "app:<name>" --color 2E7D32 --description "apps/<name>"
```

## When you add a label

Add it here first (or in the same PR), with a description and a colour, and create it on GitHub with `gh label create`. Prefer extending an existing family over inventing a new axis; the set is deliberately small, and a label used only once is usually a milestone or a title word instead.
