# GitHub repository setup (manual steps)

Things configured by hand because this machine had no `gh` CLI / API token when the rest of this repo was bootstrapped. Do these once, from the GitHub web UI, as the repo owner.

## Repository visibility

**Done.** This repo is public — confirmed via `curl https://api.github.com/repos/ramsesoriginal/lorenzo`, which now returns `200` (a private repo returns `404` unauthenticated, indistinguishable from "doesn't exist," by design). This is also what unblocked `actions/dependency-review-action` (in `security.yml`), which requires either a public repo or a paid GitHub Advanced Security add-on on a private one.

## Branch ruleset

Settings → Rules → Rulesets → New ruleset → Import a ruleset → select [.github/rulesets/main.json](../../.github/rulesets/main.json).

This gives you: no force-push/deletion of `main`, PRs required, merge commits only (squash/rebase disabled — see [ADR 0005](../adr/0005-git-branching-and-merge-strategy.md)), and `ci-summary` as a required status check.

Confirmed via the real check-runs on `main` (`curl https://api.github.com/repos/ramsesoriginal/lorenzo/commits/main/check-runs`): the matrix jobs report as `test (apps/api)` and `codeql (python)`. Both are now in [.github/rulesets/main.json](../../.github/rulesets/main.json) alongside `ci-summary`.

Re-importing the file doesn't happen automatically, though — the live ruleset (Settings → Rules → Rulesets → **main**) needs the same two contexts added by hand under "Require status checks to pass," or it'll keep enforcing only the old `ci-summary`-only list.

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
