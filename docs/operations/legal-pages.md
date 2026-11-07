# Legal pages: what to fill in and when to update them

The legal notice (Impressum) and the privacy policy are served by [`apps/legal`](../../apps/legal/README.md) ([ADR 0439](../adr/0439-legal-notice-and-privacy-policy.md)). The repository holds the text that is true of every deployment. You hold the rest. **The texts are drafts until a lawyer has reviewed them**; nothing here or in the pages says that a deployment complies with the law, and the open legal questions are listed in the ADR.

## The Pages project

Create a Cloudflare Pages project connected to the repository, named `lorenzo-legal`, production branch `main`, root `apps/legal`, output `dist`, the `NODE_VERSION` environment variable set to the Node major in the root `mise.toml`. Build with:

```bash
npm install --global corepack@latest && corepack enable && pnpm install --frozen-lockfile && pnpm run build
```

Build watch paths follow [the rule in the deployment setup](deployment-setup.md#build-watch-paths): `apps/legal/**`, `apps/brand/**`, `packages/brand/**` and `pnpm-lock.yaml`.

There is no Authgear client and no API call. The app needs one environment variable, `LEGAL_PROFILE`, below. **Without it the build fails on purpose.** A site that serves people points its custom domain at this project.

## The deployment variables

| Where | Variable | Meaning |
| --- | --- | --- |
| Pages project `lorenzo-legal` | `LEGAL_PROFILE` | The operator profile, one JSON object (below). |
| GitHub Actions variable, handed to the API at deploy | `LEGAL_URL` | The address of the legal app, for example `https://legal.example.org`. **No default**: unset, the apps show no legal links, so a deployment cannot link to another operator's notice. |
| GitHub Actions variable, handed to the API at deploy | `SUPPORT_URL` | An optional support link (a donation page, for example). Unset, no link is shown. |

`LEGAL_URL` and `SUPPORT_URL` are added to `deploy-api.yml` like `REPORT_ADDRESS` ([Going public](public-launch.md#2-the-report-address)); a change takes effect on the next API deploy, which you can start by hand.

## The operator profile

One JSON object. Every field is required unless it says otherwise; the build names each one that is missing or still holds a placeholder such as `TODO`.

| Field | Meaning |
| --- | --- |
| `changedOn` | The date you last changed the profile, `YYYY-MM-DD`. Shown as the page's date when later than the text's own. |
| `reviewedOn` | Optional, `YYYY-MM-DD`. Set only when a lawyer has reviewed the texts. While it is missing, every page says it is an unreviewed draft. |
| `operator.name`, `street`, `postalCode`, `city`, `country` | Who runs this deployment and the address they are established at (§ 5 Abs. 1 Nr. 1 DDG). |
| `operator.email` | The address people write to. It must be read. |
| `operator.secondContact` | A second quick way to be reached (a phone number, a form), or the word `none`. Whether email alone is enough is a question for the lawyer. |
| `operator.taxId` | `{"kind": "none"}`, or `{"kind": "vat" \| "wid", "value": "…"}` for a VAT identification number or a Wirtschafts-Identifikationsnummer you hold (§ 5 Abs. 1 Nr. 6 DDG). A missing value is an error, not "none". |
| `operator.reportEmail` | Optional. Where reports of unlawful content go; the operator email when absent. |
| `supervisoryAuthority.name`, `url` | The data protection authority responsible for you. |
| `providers[]` | Every provider that handles personal data: `name`, `purpose`, `location`, `transfer`, `policyUrl`. `purpose`, `location` and `transfer` are `{"de": "…", "en": "…"}`. |
| `retention.logs`, `backups`, `activityLog` | How long each is kept, as `{"de", "en"}`. |
| `gravatarLookup` | `true` or `false`: whether the API of this deployment makes the one-time Gravatar lookup (`GRAVATAR_LOOKUP_ENABLED`, default `true`). The policy describes that request only when it is `true`. |
| `support` | Optional `{"name", "url"}`: a support link the policy names as a link out. |

For a development build, `LEGAL_PROFILE_SAMPLE=1` uses [a made-up profile](../../apps/legal/src/lib/sample-profile.ts) under a "sample" banner.

## What to find out before you fill it in

Nothing here is knowable from the repository. Ask each provider and write down the answer, with the date:

- **Where each provider processes** and what it keeps: the region of the database and of the compute, the identity provider's region and data location, the hosting provider's logs.
- **Whether you have a processing agreement** with each provider that processes on your behalf, and what its sub-processors are.
- **What allows a transfer outside the EU**, where there is one (an adequacy decision, standard contractual clauses). The status of the EU-US Data Privacy Framework is the subject of a pending appeal; check the Court's own register.
- **How long** logs, backups and point-in-time recovery are kept. Lorenzo does not set these; the provider's settings do. The activity log has no limit built in.

Keep the records of processing and the processing agreements **outside this repository** if they contain personal data.

## What to re-check, and when

Change the profile, and the date in it, when:

- **a provider, a region or a retention setting changes**, or you add a provider;
- **you move or change your address, email or contact**;
- **a feature starts handling personal data differently.** The fixed text is in `apps/legal/src/lib/texts/`; a pull request that changes what Lorenzo stores or sends must change it in the same pull request. `apps/legal/tests/storage-keys.test.ts` fails for a source file that begins to use browser storage without being listed in `apps/legal/src/lib/storage-keys.ts`.

A processor that is used but not entered in the profile is caught only by a person, so ask for each change to a deployment: *is there a new provider, and is it in the profile?*

## Self-hosting

A self-hoster sets their own `LEGAL_PROFILE`, `LEGAL_URL` and, if they want one, `SUPPORT_URL`. Nothing in the repository names an operator, so another deployment never shows yours.
