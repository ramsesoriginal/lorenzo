# 0439 - The legal notice and the privacy policy: one app, one operator profile

Status: accepted, decided with the maintainer on 2026-11-07. Refines [ADR 0410](0410-the-web-shell-header-navigation-and-status-bar.md) (D19 of [docs/design/web](../design/web/README.md): the legal links and their labels). Builds on [ADR 0273](0273-app-links-registry.md) (the registry of app links) and [ADR 0007](0007-apps-layout-and-multiplicity.md) (one directory per deployable app).

**Everything this decision produces is a draft for legal review.** No page, document or test it creates says that Lorenzo or an operator "is compliant". Every statement of law below is a starting point checked against the sources named, and the open questions are listed at the end.

## Context

[v1.0](../../v1.0.md) lists a privacy notice as New. The shell already has the places for two legal links: `WebBottom.astro` shows "Legal notice" and "Privacy policy" in the "Apps and about" sheet only when an app passes `legal.notice` or `legal.privacy`, and no app does. The pages do not exist.

What the system does with personal data was checked on 2026-11-07 against the code, the docs and a real browser (Chromium, the repository's real-API test stack, every web app signed out and signed in):

- **Held by the API:** an account (Authgear subject id, a read-only cache of the verified email, optional nickname and profile fields, an uploaded picture, hashed personal access tokens), memberships and seats, `created_by` and `updated_by` on entries, a per-library activity log without a retention limit ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)), notifications, and whatever a game master writes about players and characters. The loot-bot holds a Discord user id and encrypted tokens; the mobile apps keep encrypted local snapshots. A public repository shows its Owners' display names ([ADR 0299](0299-what-a-public-repository-says-about-its-publisher-and-hides-about-its-libraries.md)).
- **Held in a browser** (signed in, first page of each app): the Authgear web SDK's `idToken` (which carries the email), `refreshToken` and `oidcCodeVerifier` in `localStorage`; `lorenzo:lastTenant`; Bench's `bench:workspace` even when signed out; and cached `/me` and `/tenants` reads in `sessionStorage`. From the code only: return paths and an invite token in `sessionStorage`, Bench's theme and layout keys, `lorenzo:lastHolder`, the inventory catalogue cache, Maps' look and projection keys, and the unsaved drafts that Writing keeps in IndexedDB.
- **Requests to third parties:** one. `GET /users/{id}/picture` answers with a 302 to `https://www.gravatar.com/avatar/<sha256 of the email>` for an account with an email and no uploaded picture, and the account hub's profile page loads it in an `<img>`. Fonts are self-hosted; no analytics or error tracking is initialised; the API sets no cookie.
- **Not in the repository:** the region of the Neon database, the retention of logs, backups and point-in-time recovery, and any processor agreement.
- Lorenzo is AGPL-3.0 and meant to be self-hostable, so a page that names an operator cannot be part of the code every deployment copies. `REPORT_ADDRESS` (an Actions variable handed to the API at deploy) is the precedent for operator-specific settings.

## Decision

**1. A notice and a policy are published, in German and English.** § 5(1) DDG (text from gesetze-im-internet.de; the version date is not recorded here) applies to "geschäftsmäßige, in der Regel gegen Entgelt angebotene digitale Dienste". Whether a service with a donation link and members who contribute to hosting costs falls under it is a legal question. The decision does not wait for the answer: the pages are published and the question goes to the lawyer. German is the binding text; English is a translation alongside it.

**2. One new static app, `apps/legal`**, in Astro like the others, deployed to its own Cloudflare Pages project `lorenzo-legal`. It serves one canonical page per language and no copy lives in any other app:

| Page | German | English |
| --- | --- | --- |
| Legal notice | `/de/impressum/` | `/en/legal-notice/` |
| Privacy policy | `/de/datenschutz/` | `/en/privacy-policy/` |

Each page links to its counterpart in the other language, shows the date it last changed, and the history is git's. The app has no Authgear client, no API call and no storage of its own.

**3. The operator profile.** What is specific to one deployment is not in the repository. `apps/legal` reads one structured value at build time (`LEGAL_PROFILE`, a Pages environment variable holding JSON, validated against a schema in the app):

- The operator: name, postal address, country, email address, an optional second contact, and the tax identification number or an explicit `none`. An explicit `none` is required for each optional-but-must-be-declared item, so that "I have none" and "I forgot" differ.
- The providers the deployment uses: for each, its name, what it does, where it processes (its region), the safeguard for a transfer outside the EU, and a link to its own policy.
- The retention periods of the deployment (logs, backups, the activity log).
- An optional support link (item 6).
- `reviewed_on`, a date, set only when a lawyer has reviewed the texts. While it is unset, every page says in its first lines that it is a draft that has not been reviewed.

**The build fails** with the names of the missing fields when a required one is unset or holds a placeholder. A development build may use a sample profile that is only enabled by an explicit flag and prints a visible "sample" banner on every page. The repository holds no real name, address, tax number or contact. A self-hoster sets their own profile or the build fails.

**4. The fixed text and the profile.** The parts that are true for every deployment (what Lorenzo stores and why, the rights people have and what the product offers for each) are German and English templates in the app. The profile fills the rest. The policy is written from the verified inventory only; a fact that is not known is a failing build, not a sentence.

**5. The links are wired through the shell and the registry.**

- `GET /app-links` ([ADR 0273](0273-app-links-registry.md)) gains `apps.legal` from a `LEGAL_URL` setting. **It has no default**, unlike the other apps: a deployment that has not set it shows no legal links ([ADR 0410](0410-the-web-shell-header-navigation-and-status-bar.md)'s `legal` props are already omitted when unset), and cannot link to another operator's notice by accident. The official deployment sets it.
- Each web app passes `legal` to `AppPage`; `bindShell` replaces the build-time addresses with the registry's, with the fallback rule of ADR 0273.
- `@lorenzo/app-shell` gains a `lang` property (`en` or `de`, default `en`) that sets `<html lang>`, chooses the labels and chooses the link target. The labels are:

| | English | German |
| --- | --- | --- |
| Notice | Legal notice (Impressum) | Impressum |
| Policy | Privacy policy | Datenschutzerklärung |

This amends the wording of D19 in `docs/design/web`, which turned down the German names. The design document is not edited by this decision; its owners update it.

- Every web app's test asserts that both links are present and resolve (a per-app shell test), and the existing accessibility and phone checks cover them.

**6. A support link.** `GET /app-links` carries an optional support address from a `SUPPORT_URL` setting, as `REPORT_ADDRESS` is handed to the API. The "Apps and about" sheet shows it, labelled "Support Lorenzo", next to "Source code" only when set. It is a plain link. No widget, script or image of the support service is ever embedded, so no page makes a third-party request because of it. The policy names it as a link out.

**7. The avatar is copied once and never fetched again.** The redirect to Gravatar is removed.

- **When:** at the moment the verified email is first cached ([ADR 0075](0075-sync-email-via-userinfo-not-access-token.md)), if the account has no uploaded picture and has not been checked, the API asks `https://www.gravatar.com/avatar/<sha256 of the email>?d=404&s=200` once, with a short timeout, without following redirects, under the content-type allow-list and size cap of an upload ([ADR 0056](0056-profile-pictures.md)). A `200` is stored as the account's own profile picture. A `404` stores nothing.
- **A marker** on `app_user` (`gravatar_checked_at`) records that the question was asked, so it is never asked again. A network failure does not set it and does not fail the request; the retry is bounded.
- **No backfill.** The migration sets the marker for every account that already has an email, so existing accounts are never looked up. They keep what they have and can upload a picture.
- **The picture is theirs from then on.** Deleting it leaves the account without one; nothing refills it. The policy says so in a few lines, and that is also the objection.
- `GET /users/{id}/picture` serves the stored picture or answers `404`. `picture_url` stays as it is.

**8. Other clients link to the same pages.** The loot-bot (its help text), the CLI (README and `--help`), and the Android and iOS apps (a settings screen) link to the notice and the policy, resolved from the registry where the client can, and have no texts of their own. The bot's use of a Discord user id and its tokens, and the apps' local encrypted snapshots, are in the policy.

**9. It ships as one block.** The app, the texts, the shell change, the per-app wiring, the avatar change and the support link are stacked PRs that land on a feature branch and from there on `main` in one merge commit ([AGENTS.md](../../AGENTS.md)). The texts describe the state after that merge; none describes a state that is not true yet. Because `LEGAL_URL` has no default and the legal build fails without a profile, nothing is linked or published before the operator sets both.

**10. Keeping the texts true.** A change that adds an app, a stored key, a processor or a field of personal data must update the profile and the templates. This is enforced, not remembered:

- a checklist step in [adding-an-app.md](../guides/adding-an-app.md) (legal links wired, keys declared);
- a test in `apps/legal` that scans `apps/*/src` for `localStorage`, `sessionStorage` and `indexedDB` use and fails for a key that is not declared in the app's list of storage keys;
- the per-app shell tests of 5;
- a test that no app's start page requests a host outside its own, the API and the identity provider.

A new processor is a profile entry, and the schema requires every field of an entry, so a half-filled processor fails the build. A processor that is used but never entered is caught only by review, so the operations page lists it as a step for any change to a deployment.

## Not decided here

- Whether the law requires a notice, and who is the controller or the processor for each provider and for a game master ([Open questions](#open-questions-for-legal-review)).
- A notice-and-action route and a takedown process beyond `REPORT_ADDRESS` and the operator delist ([ADR 0303](0303-operator-delist.md)), a way for a person to download their data, retention and pruning of logs, backups and the activity log, minors, and the Owner's public display name. Each is a follow-up issue, not part of this block.
- The contents of the operator profile for any deployment. They come from the operator.
- A consent banner. None is needed while the browser keys are the ones listed, and the lawyer is asked to confirm.

## Open questions for legal review

All unverified; none is an assertion.

1. The current wording of § 5 DDG and whether a free service with a donation link and cost contributions is "in der Regel gegen Entgelt"; whether a tax identification number held for an earlier activity must be stated (Nr. 6); whether email alone meets "schnelle elektronische Kontaktaufnahme und unmittelbare Kommunikation" (Nr. 2); whether the "Apps and about" link is "unmittelbar erreichbar"; whether § 18 MStV applies.
2. Whether any key in the table of browser storage is not "unbedingt erforderlich" under § 25 TDDDG (in particular `bench:workspace`, the catalogue cache and the Writing drafts), so that a banner would be needed.
3. The avatar copy: the basis (Art. 6(1)(f) GDPR), the balancing, the information duty when sign-up is Authgear's page, the transfer to the United States and Automattic's status under the EU-US Data Privacy Framework, and whether the purpose of the email is compatible (Art. 6(4)).
4. Controller or processor for Authgear, Neon, Google Cloud, Cloudflare, Discord and a game master; the Art. 28 agreements; each provider's region and sub-processors; the transfer basis for each. The status of the appeal against the Data Privacy Framework (C-703/25 P).
5. Whether a notice-and-action route (Art. 16 DSA) and a contact point (Art. 11) apply, and what § 7 DDG's liability limits require of a host that serves public repositories.
6. Minors (Art. 8 GDPR), retention and erasure when `created_by` is cleared and content stays, and the legal basis for showing an Owner's display name.

## Consequences

- One canonical place for both pages, one operator profile, and no operator detail in the repository. Self-hosting means setting a profile.
- The shell grows a language property; the first non-English interface label set is in `@lorenzo/app-shell`. An English-only deployment is unchanged.
- The API loses a redirect and gains one outbound call per new account and a migration (`gravatar_checked_at`). People without an upload no longer get an automatic avatar unless they had a Gravatar at sign-up.
- A new app, `apps/legal`, needs the steps of [adding-an-app.md](../guides/adding-an-app.md): `mise.toml`, CI, release-please, an `app:legal` label and an entry in [apps/README.md](../../apps/README.md).
- Nothing in this decision declares any deployment compliant. The texts stay drafts until `reviewed_on` is set.
