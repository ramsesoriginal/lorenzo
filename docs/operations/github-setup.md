# GitHub repository setup (manual steps)

Things configured by hand because this machine had no `gh` CLI / API token when the rest of this repo was bootstrapped. Do these once, from the GitHub web UI, as the repo owner.

## Repository visibility

Settings → General → Danger Zone → Change visibility → **Public**. This repo is currently private — confirmed via `curl https://api.github.com/repos/ramsesoriginal/lorenzo`, which returns `404` unauthenticated (that's GitHub's response for both "doesn't exist" and "private, no access," by design). That mismatches the stated intent of this being a public showcase, and it's also a real functional problem: `actions/dependency-review-action` (in `security.yml`) requires either a public repo or a paid GitHub Advanced Security add-on on a private one — it will keep failing on every PR until this is flipped.

## Branch ruleset

Settings → Rules → Rulesets → New ruleset → Import a ruleset → select [.github/rulesets/main.json](../../.github/rulesets/main.json).

This gives you: no force-push/deletion of `main`, PRs required, merge commits only (squash/rebase disabled — see [ADR 0005](../adr/0005-git-branching-and-merge-strategy.md)), and `ci-summary` as a required status check.

`apps/api` exists now, so this is actionable: once it's merged to `main` and you've watched a few real CodeQL runs against actual Python source, confirm the exact check names GitHub reports for the matrix jobs and add them to the ruleset's `required_status_checks` too.

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
