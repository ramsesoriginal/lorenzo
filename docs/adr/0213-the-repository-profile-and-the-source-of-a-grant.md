# 0213 - The repository profile, its cover, and the source of a grant

Status: accepted, decided with the maintainer on 2026-10-08. Slice D1 of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md), tracked in #548. Extends [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) and [ADR 0056](0056-profile-pictures.md); the lengths and counts RFC 0038 left to measuring are set here.

## Context

A repository says almost nothing about itself: `tenant` has a name, a slug, a description and a picture. [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) makes repositories discoverable and copyable by any logged-in user, which needs a summary, a licence, credits, tags, a system, languages and a cover, a `visibility` and a `preview` switch to hang the later slices on, and a way to tell a grant an Owner made from one a library will make by itself. This slice is the data and its read and write routes. Nothing in it makes a repository public: the value is refused until the gates of RFC 0038 §6 exist, and none of the public read, Discover or the preview is built here.

## Decision

### The table

`repository_profile`, one row for each repository tenant, `tenant_id` its primary key:

| Column | Meaning | Limit |
| --- | --- | --- |
| `visibility` | `private` or `public`; default `private` | the API refuses `public` for now, below |
| `preview` | `off`, `showcase` or `public`; default `showcase` | the three values; it means nothing until a repository is public ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §5) |
| `summary` | one or two plain sentences for a listing; default empty | 280 characters, on one line |
| `licence_label`, `licence_url` | the licence's name (a name from a short list or the author's words) and an optional link to its text; both null is "no licence stated" | label 1 to 80 characters; a link needs a label |
| `credits` | who made it, a list of `{name, role, url}`; default empty | at most 20; name 1 to 80, role up to 60, optional link |
| `tags` | free-text labels for search, lower case, without repeats | at most 12, each 1 to 32 characters |
| `system` | the game system, one value, kept as written | up to 40 characters |
| `languages` | the languages the content is written in, as lower-case codes (`en`, `de`, `pt-br`) | at most 8 |
| `cover_picture_id` | the cover, a row of the blob table that holds every profile picture ([ADR 0056](0056-profile-pictures.md)); null for none | the pictures' types and size cap |
| `updated_by`, `updated_at` | who last changed it and when | |

- **The limits are generous for a listing and are not measured.** RFC 0038 left them to measuring the seeded repositories and the Discover spike. They are constants in one place (`schemas/repository_profiles.py`), repeated as `CHECK` constraints for the counts and lengths a row can break, and a later slice raises one by editing both with a migration.
- **Text is plain.** A one-line field has its whitespace runs, line breaks included, made into single spaces and its ends trimmed; anything not printable is refused. Tags are trimmed, lower-cased and de-duplicated, in the order given. The system keeps its case (`D&D 5e`), since it is shown; a blank system is no system. A language is a code of two or three letters, optionally followed by up to two subtags, lower-cased.
- **A link is `https` only.** It must start with `https://`, have a host, hold no user name or password and no whitespace, and be at most 500 characters; the scheme is stored in lower case and the `CHECK` on `licence_url` is the same rule. Any other scheme (`http`, `javascript`, `data`, `mailto`) or a link without a host is a `422`. The pages that later show a link give it `rel="nofollow noopener"`.
- **One profile for each repository, made three ways.** `POST /tenants` with `kind = repository` makes it in the same transaction, a migration made one for every repository that exists, and a repository with none for any other reason gets its private, default one the first time its profile is read or written. A trigger refuses a row for a play tenant, as one on `campaign` refuses a campaign in a repository.
- **Row-level security and `repository_access`.** `tenant_isolation` and `FORCE ROW LEVEL SECURITY` as every tenant table, and `repository_read`, because a library the repository is granted to reads it through the gated read. [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §2 named the table among those that are not content. What that says holds: a copy never carries the profile (a test copies a repository and finds no profile row on the library), and `plan_copy` and the update engine read the tables they always read. But the list that carries the `repository_read` policy is `REPOSITORY_CONTENT_TABLES`, which already holds `repository_release` and the released rows, and it is the one the table is in, so the test that every tenant table is classified and the test that a granted library sees a table only inside the gated read and never writes it cover the profile.
- **No foreign key to another tenant table**, so none is composite. The cover's key is to the blob table, which has no tenant ([ADR 0056](0056-profile-pictures.md)): `ON DELETE SET NULL`, and unique, so two profiles never share a picture.
- **Migration** `a1d4c7e9b203`.

### Reading and writing it

All under `/tenants/{tenant_id}`, in `routers/repository_profiles.py`:

| Route | Who | What |
| --- | --- | --- |
| `GET /profile` | any member of the repository | the profile |
| `PATCH /profile` | an Owner | changes the fields named; a field left out is unchanged |
| `GET /profile/cover` | any member | the cover's bytes with its type; `404` without one |
| `PUT /profile/cover` | an Owner | `multipart/form-data`, a `file`; sets or replaces the cover; `204` |
| `DELETE /profile/cover` | an Owner | removes the cover and its picture; `204`, also when there is none |
| `GET /repositories/{repository_id}/profile` | a member of a library the repository is granted to, once it is published | the same profile, through the gated read |
| `GET /repositories/{repository_id}/profile/cover` | as above | the cover |

- **The shape**, `RepositoryProfileOut`: `visibility`, `preview`, `summary`, `licence` (`{label, url}` or `null`), `credits` (a list of `{name, role, url}`), `tags`, `system`, `languages`, `has_cover` and `updated_at`. The cover is not inlined: `has_cover` says whether to ask for it.
- **`PATCH` takes the same fields, all optional, and refuses an unknown one** (`422`). `null` clears `licence` and `system`, `[]` clears a list, `""` clears the summary; `null` for `visibility`, `preview`, `summary`, `credits`, `tags` or `languages` is a `422`, since leaving a field out already keeps it. A request that changes nothing is accepted. Everything is checked before anything is written, so a refused request keeps none of its fields.
- **`public` is refused**: `visibility: "public"` answers `422`, type `public-repositories-not-available`, title "Public repositories are not available yet", detail "Public repositories are not available yet. This repository stays private.", and changes nothing, not even the other fields in the request. The database accepts the value, so slices D2 to D6 lift the refusal in one place. `private`, and any value of `preview`, are accepted.
- **Only an Owner writes it**, as publishing is: an Organizer reads it and is refused with `403 repository-management-forbidden`. Whether an Author may edit it is [RFC 0040](../rfcs/0040-authors-and-invites.md)'s; the check is the Owner check the other repository routes use, so that slice changes it where it decides.
- **A play tenant has no profile**: every route answers `409 not-a-repository`. A non-member gets the `404` every tenant route gives, and a library the repository is not granted to, or a repository that is a draft, gets `404 repository-not-found` from the gated routes, as every read of a repository does.
- **The cover** takes the allowed types and the size cap of every profile picture (`image/png`, `jpeg`, `webp`, `gif`; 2,000,000 bytes unless the deployment changes it), and a `422 invalid-profile-picture` otherwise. Replacing it overwrites the one picture row, so one blob is kept for each repository. The route that deletes a repository ([ADR 0184](0184-deleting-a-tenant.md)) deletes its cover's blob first, because the cascade from the tenant reaches the profile row and not the blob table. The cover is read with a token, as every route here: making a private repository's picture authenticated and a public one's open is slice D6 of RFC 0038, with the hub change a browser image needs.
- **The activity log** records `repository.profile_updated` with `fields=` and the names of the fields changed, never their text, and `repository.profile_cover_set` and `repository.profile_cover_removed`.

### The source of a grant

`repository_subscription.source`, `invited` or `public`, default `invited`, a `CHECK` on the two values. Every grant that exists is an invited one, which is what the default gives them.

- **The repository's side can only write an invited grant.** The insert policy `repository_subscription_grant` is now `repository_tenant_id = app.tenant_id AND source = 'invited'`. A `public` grant is a library's own, which comes with the public read in slice D2 and its own policy; until then nothing can write one. `PUT /tenants/{id}/subscribers/{subscriber_tenant_id}` writes `invited` explicitly.
- **Nothing else changes about grants.** The subscribers list, revoking, `lorenzo repo` and the update engine see only invited grants until D2, so they need no change yet. The rule RFC 0038 §1 gives for a library that holds both (the invitation outranks a public copy, so a repository going private does not cut off a library it invited) is built where a public grant can first exist, with D2.

## Not in scope

- Accepting `public`, and everything that depends on it: the public branch of the read gate, the library-less routes, copying a public repository (D2), the Discover listing and its read policy on the profile (D3), the preview, the showcase entries and the gated entry read (D4), the flips (D5), the gates, which include the operator's delist, the quotas on pictures, the publisher's identity and the authentication of a private repository's picture (D6), and deprecate (D8).
- Screens: Studio's profile and visibility screens and the storefront (RFC 0036 T5, T7, S6), and the command line. The profile is an API and a table so far.
- The profile of a repository in the notifications of a publish, in `TenantOut` and in `GET /tenants`. Discover reads it where it needs it.
- The orphaned blob a tenant's own profile picture leaves when the tenant is deleted, which is older than this slice and unchanged by it.

## Consequences

- The API change is additive: new routes, a new column on a table no response shows, and no accepted break in `openapi-breaking-accepted.txt`. The generated client and the command line's models gain the new routes and schemas.
- The wall of [ADR 0002](0002-multi-tenancy-shared-schema-rls.md) is not widened: the profile is readable beyond its tenant only through the gated read ADR 0118 already drew, `FOR SELECT`, for a granted library and a published repository, and the RLS tests of ADR 0118 run over it.
- Every repository now has a row, so the slices that list or read repositories join it rather than create it; a repository made by a test or a script without one is made good by the first read.
- Raising a limit later is a constant and a migration, which is the price of keeping the counts as database constraints too.
