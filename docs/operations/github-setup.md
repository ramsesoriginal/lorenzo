# GitHub repository setup (manual steps)

Things configured by hand because this machine had no `gh` CLI / API token when the rest of this repo was bootstrapped. Do these once, from the GitHub web UI, as the repo owner.

## Repository visibility

**Done.** This repo is public — confirmed via `curl https://api.github.com/repos/ramsesoriginal/lorenzo`, which now returns `200` (a private repo returns `404` unauthenticated, indistinguishable from "doesn't exist," by design). This is also what unblocked `actions/dependency-review-action` (in `security.yml`), which requires either a public repo or a paid GitHub Advanced Security add-on on a private one.

## Branch ruleset

The ruleset is [.github/rulesets/main.json](../../.github/rulesets/main.json). It gives `main`: no force-push or deletion, PRs required, merge commits only (squash/rebase disabled, see [ADR 0005](../adr/0005-git-branching-and-merge-strategy.md)), and three required status checks:

- **`ci-summary`**, the aggregate job in `ci.yml`. It always runs and waits on every other CI job: skipped counts as fine, failed or cancelled does not. **A job that should gate a merge must be in `ci-summary`'s `needs`**; one left out is never waited for.
- **`codeql (python)`** and **`codeql (javascript-typescript)`** from `security.yml`, which runs on every PR.

Individual `test (<node>)` legs are deliberately **not** required: PR CI only runs the nodes a change can affect ([ADR 0148](../adr/0148-dependency-aware-pr-ci.md)), and a required check that is skipped never reports, so it would block the merge forever. Don't add one back. New apps need nothing here; `ci-summary` already covers them.

Applying it the first time: Settings → Rules → Rulesets → New ruleset → Import a ruleset → select the file. Changing it later is not automatic: the file and the live ruleset are separate, so edit the file and apply the same change to the live ruleset, then confirm with `gh api repos/ramsesoriginal/lorenzo/rulesets/<id>`. A blanket `PUT` from the file is safe only if the file lists every field the live ruleset has, which it does since 2026-09-30; fetch the live one first and compare.

## Actions: allow workflows to open pull requests

Settings → Actions → General → Workflow permissions → check **"Allow GitHub Actions to create and approve pull requests"**.

GitHub disables this by default on every repo, regardless of visibility. `release-please-action` (`.github/workflows/release.yml`) needs it to open its release PRs — it authenticates as the workflow's own `GITHUB_TOKEN`, unlike Dependabot, which has a separate exemption built into GitHub and opens PRs fine either way. Confirmed via a real failed run: release-please got as far as creating its release branch and commit, then failed on the PR-creation API call with `GitHub Actions is not permitted to create or approve pull requests.` Nothing to fix in the workflow itself — this is purely the one-time repo setting.

## Security

Settings → Code security:

- Enable **Dependabot alerts** and **Dependabot security updates**.
- Enable **Secret scanning** and **push protection**.
- Enable **Private vulnerability reporting** (this is what [SECURITY.md](../../SECURITY.md) points people at).

## Repository settings

Settings → General:

- Description + topics (suggestion: `dnd`, `ttrpg`, `worldbuilding`, `gamemaster-tools`).
- Features: enable **Discussions** (referenced from the issue template config); Wiki off (`docs/` replaces it).
- Pull Requests: "Allow merge commits" on; "Allow squash merging" and "Allow rebase merging" off (the ruleset also enforces this); "Automatically delete head branches" **off**.

## Pages

Settings → Pages → Source: **GitHub Actions**, once a web frontend actually needs deploying.

## Optional, once every laptop is set up for it

Commit signing (SSH signing is the low-friction option, since this repo already uses SSH remotes) — then add a `required_signatures` rule to the ruleset. Not enabled yet so it doesn't lock out a laptop mid-setup.
