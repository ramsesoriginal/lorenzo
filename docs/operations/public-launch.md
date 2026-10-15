# Going public: what to set, and in what order

Public repositories ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)) are built and **off**. This is the list for switching them on in a deployment. The build is done (the gates D1 to D6: [ADR 0290](../adr/0290-the-flips-as-routes-and-the-visibility-switch.md), [0292](../adr/0292-discover-the-listing-and-the-storefront.md), [0293](../adr/0293-the-preview.md), [0298](../adr/0298-quotas-on-a-repository.md), [0299](../adr/0299-what-a-public-repository-says-about-its-publisher-and-hides-about-its-libraries.md), [0300](../adr/0300-authentication-on-a-private-repositorys-picture.md), [0301](../adr/0301-release-fan-out-and-cooldown.md), [0303](../adr/0303-operator-delist.md)); what is left is configuration and the edge rule, which are the operator's.

## 1. The edge rate-limit rule (before the switch)

Discover and the copy of a public repository are routes that need a signed-in user and are cheap to call in a loop. The rule that protects `/invites/*` ([Rate-limiting the invite-link endpoints](invite-link-rate-limiting.md)) is extended to name them: see its section "Discover and the copy of a public repository". Put it in place before the API has a public production address, together with the invite rule, so there is one rule set to configure.

## 2. The report address

A public repository's storefront has a **Report this repository** link, a `mailto:` to the address in `REPORT_ADDRESS`. Lorenzo has no report inbox: the address is a mailbox someone reads. Unset, there is no link.

Set it as a GitHub Actions variable (*Settings, Secrets and variables, Actions, Variables*) named `REPORT_ADDRESS`; `.github/workflows/deploy-api.yml` hands it to the API on the next deploy. Blank counts as unset.

## 3. The switch

Set the Actions variable `PUBLIC_REPOSITORIES_ENABLED` to `true` and deploy the API. Nothing else changes in the hub: its Discover link and its Make public button follow what the API says (`GET /discover/facets` carries `enabled`). Unset, or anything but `true`, means off: the flip routes answer `public-repositories-not-available` and Discover shows nothing.

## 4. Settings that already have a default

None of these needs setting. They are API environment variables, so changing one means adding it to `env_vars` in `.github/workflows/deploy-api.yml` first.

| Variable | Default | What it does |
| --- | --- | --- |
| `REPOSITORY_MAX_ENTRIES` | `30000` | Most entries a repository holds, counted when something adds one by hand ([ADR 0298](../adr/0298-quotas-on-a-repository.md)). The copy and update engines are exempt. `0` is no limit. |
| `REPOSITORY_MAX_PICTURE_BYTES` | `20000000` | Most picture bytes on a repository's entries in all. |
| `REPOSITORY_PICTURE_MAX_BYTES` | `10000000` | Most bytes in one such picture. The global `PICTURE_MAX_BYTES` is also 10 MB, so this is no stricter until lowered. |
| `RELEASE_COOLDOWN_SECONDS` | `300` | Least time between two releases of a public repository ([ADR 0301](../adr/0301-release-fan-out-and-cooldown.md)); a release inside it is `429 release-cooldown`. The flip to public, edits and making an earlier release current are never held back. `0` is off. |
| `RELEASE_FANOUT_CHUNK_SIZE` | `250` | Libraries told in one transaction when a release is announced. |
| `RELEASE_FANOUT_SWEEP_CHUNKS` | `20` | Chunks one sweep writes before it leaves the rest for the next. |
| `RELEASE_FANOUT_SWEEP_INTERVAL_SECONDS` | `60` | Least time between two sweeps a process starts. |

## 5. Dealing with an abusive repository

An operator (an account with the `platform-operator` role, [ADR 0057](../adr/0057-platform-operations.md)) takes a repository off Discover with a reason; its Owners are told, libraries that copied it keep their copies and stop updating from it, and its members still reach it ([ADR 0303](../adr/0303-operator-delist.md)):

```bash
lorenzo api PUT /admin/repositories/<repository-id>/delist --data '{"reason": "Why it was taken off"}'
lorenzo api GET /admin/repositories/delisted
lorenzo api DELETE /admin/repositories/<repository-id>/delist   # lists it again
```

Suspending an account (`PUT /admin/users/<id>/suspend`) delists every repository it owns; un-suspending does not list them again. This is the lever, not a takedown process: who may ask for it and how a complaint is judged are not designed ([RFC 0038 §8](../rfcs/0038-public-repositories-and-discovery.md#8-operations)).

## 6. What to know

- **Announcements can be late, not lost.** A release writes one row and the notices are written after the response, by a sweep at start-up and at most once a minute on a signed-in request. There is no scheduled job in production, so with no traffic a stranded batch waits for the next request or restart. An hourly authenticated call from Cloud Scheduler ([ADR 0095](../adr/0095-loot-bot-notification-dms.md)'s pattern) would close that gap; it would also keep the Neon database awake, so it is optional.
- **The cooldown's 300 seconds** rests on a measured cost per statement, not on the real Cloud Run to Neon round trip; if releases of large repositories feel slow to announce, time one `SELECT 1` from the service and revisit it.
- **The terms line** the Owner agrees to, and the Report link, are described in [ADR 0299](../adr/0299-what-a-public-repository-says-about-its-publisher-and-hides-about-its-libraries.md).
