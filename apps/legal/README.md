# Lorenzo legal pages

Static Astro app that serves the legal notice (Impressum) and the privacy policy, in German and English, for one deployment of Lorenzo ([ADR 0439](../../docs/adr/0439-legal-notice-and-privacy-policy.md)).

| | German | English |
| --- | --- | --- |
| Legal notice | `/de/impressum/` | `/en/legal-notice/` |
| Privacy policy | `/de/datenschutz/` | `/en/privacy-policy/` |

**Every text is a draft for legal review.** A page says so in its first lines until the operator profile carries a `reviewedOn` date. None of it says that Lorenzo or an operator complies with the law.

## What is in the repository, and what is not

The fixed text (what Lorenzo stores and does, from the code and the ADRs) is in `src/lib/texts/`, German and English side by side so one cannot grow a section the other lacks. Everything specific to one deployment is the **operator profile**: the operator's name and address, the providers, the retention periods, the supervisory authority and the review date. It is never kept in the repository. The build reads it from `LEGAL_PROFILE` (JSON, checked by `src/lib/profile.ts`) and fails, naming each missing or placeholder field, when it is incomplete. `LEGAL_PROFILE_SAMPLE=1` builds a made-up operator under a "sample" banner for development; `pnpm run dev` sets it.

What to put in the profile, and when to change it, is in [Legal pages](../../docs/operations/legal-pages.md).

## Keeping the policy true

`src/lib/storage-keys.ts` lists what the web apps keep in a browser; the policy prints it. `tests/storage-keys.test.ts` finds every source file of the web apps and shared packages that uses `localStorage`, `sessionStorage` or `indexedDB` and fails for one that is not listed, so a new key cannot ship without the policy being looked at.

## Commands

```bash
mise run //apps/legal:dev     # http://localhost:4330, sample profile
mise run //apps/legal:test
mise run //apps/legal:lint
LEGAL_PROFILE="$(cat profile.json)" mise run //apps/legal:build
```
