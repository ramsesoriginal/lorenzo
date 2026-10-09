# 0228 - Bench: the LIVE banner

Status: accepted, decided with the maintainer on 2026-10-09. The last interface piece of B3 in [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) (section 6) and of slice W-B in [RFC 0042](../rfcs/0042-bench-workbench-interface.md). Builds on [ADR 0227](0227-bench-stat-values-and-tags.md) and [ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md) (a repository is read live by the libraries that use it).

## Context

An edit in a repository reaches the libraries that copied it without a release: they read it live and see it when they next check for updates ([ADR 0194](0194-user-facing-terminology.md) for the words). An author who does not know that edits a repository as if it were a draft. RFC 0039 asked for a banner that says so wherever a published repository is edited.

## Decision

- **A banner under the title bar**, shown when the open repository is published (`published_at` is set on `GET /tenants/{id}`): a "Live" pill and *Libraries that copied this repository see your edits when they next check for updates.* The words are those of the prototype.
- **Hide lasts until the page is loaded again.** It is a notice about what editing does, not a setting, so it is not remembered.
- **A draft repository has no banner**, since nobody sees its edits yet.
- **The read is part of loading the session** and a failed read means no banner, never a failed sign-in: the banner is a notice, and a missing one must not stop the editor from opening.
- **The sample page** (no sign-in) has no banner until a palette command, "Sample: publish the repository", turns it on, like its other stand-ins for what a server does, so the banner can be tested in a browser.

## Not here

- **"Edited since release X"** for a public repository waits for the release ledger of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md), which the API does not have yet. Until then published is the only case there is, and the banner says nothing about releases.
- The banner is read when the page loads; publishing or unpublishing from elsewhere shows after a reload.

## Consequences

- Closes the interface side of B3. What is left of it is trying stats and tags by hand and a browser test against the real API.
