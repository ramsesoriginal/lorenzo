# 0300 - Authentication on a private repository's picture

Status: accepted, slice D6d of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §6 item 7; "authentication alone" is the RFC's recommended answer to its open question about who may see a private repository's picture, taken as the default until the maintainer says otherwise. Tracked in #747.

## Context

`GET /tenants/{tenant_id}/picture` has had no authentication at all since [ADR 0056](0056-profile-pictures.md), so that a plain `<img src>` could show a tenant's picture. For a play tenant that is a profile picture, and it stays open. A repository is different once repositories can be private: the picture is the Owner's, not something every visitor of the API should be able to fetch by id.

The cover routes are not the problem. `GET /tenants/{id}/profile/cover`, `GET /tenants/{id}/repositories/{id}/profile/cover` and `GET /repositories/{id}/profile/cover` have asked for a signed-in user since [ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md) and [ADR 0287](0287-who-may-read-a-public-repository.md), and the hub already fetches a cover with the token. A campaign belongs to a play tenant, never to a repository (a trigger keeps it so), so a campaign's picture is untouched.

## Decision

### Who gets a tenant's picture

| Tenant | No token | A valid token |
| --- | --- | --- |
| Play tenant | The picture, as before | The picture |
| Public repository | The picture | The picture |
| Private repository | `404`, as for a tenant with no picture | The picture, member or not |
| A tenant with no picture, or no tenant | `404` | `404` |

A repository is **private** when its profile's `visibility` is not `public`; a repository with no profile row has said nothing and is private. Anyone signed in may read a private repository's picture: authentication alone, not membership or a grant. A membership rule would also have to count the holder of an invite link and a library with a grant, and the picture is the one thing of a repository that Discover, a library's shelf and an invite page all show before anyone is a member.

### A request with no token gets a `404`, not a `401`

A `401` for a private repository would tell a request with no token which ids are private repositories that have a picture. The route answers it exactly as it answers a tenant that has no picture or does not exist: the same status, problem type, title and detail (only the id in the detail differs). Nothing that was an answer before changes for a play tenant or a public repository. The cost is that a client that lost its token is told "not found" and not "log in"; none of the apps' calls can lose it silently, since each fetches with the token it holds.

A token that **is** sent is checked whatever the tenant: a bad, expired or revoked one is the usual `401`, a suspended account the usual `403`. That answer depends on the token alone, so it tells nothing about the id.

### How the route takes an optional token

`dependencies.get_optional_user` (`OptionalUser`) reads the `Authorization` header itself, returns `None` for no header or one that is not a bearer token, and otherwise verifies the token and resolves the user exactly as `get_current_user` does (an Authgear token or a personal access token). It is read from the header and not through `HTTPBearer`, so the route's entry in the OpenAPI document gains no security requirement: nothing in the schema changes for a client, only the description of the route. The route is still deliberately outside every router-level auth dependency (ADR 0056).

### The apps fetch the picture with the token

An `<img src>` cannot send a bearer token, so every place that shows a repository's `/tenants/{id}/picture` fetches it with the token and shows it from a `blob:` address. Of every app, only the account hub shows a tenant's picture:

- **Account hub, Shelf** (`RepositoriesPanel`): the card and the page of a repository, with its first letter where it has no picture or none that can be read.
- **Account hub, Studio** (`Repository`): the picture control on a repository's Overview, which asks for the picture afresh after an upload and shows nothing after a removal.
- **Account hub, a library** (`Tenant`): the same control for a play library. Its picture is open, and is fetched with the token like the rest for one code path.
- **Account hub, an invite link** (`JoinInvite`): the preview of an invite is public and carries the repository's picture address. Someone logged in sees the picture fetched with the token; someone who is not asks for it as it is, which a public repository answers and a private one does not, so there is no picture for them before they log in.
- **Discover** and a storefront already fetched a cover with the token. The helper is now shared (`lib/pictureFetch.ts`), and a tenant's picture is kept once for each tenant until it is changed or removed.

Not changed, because none can show a repository's picture: **inventory-web**, **beings**, **bench** (their pictures are an entry's own, read through the entry's payload routes, which asked for a token all along), the **loot bot** and the **CLI** (they show a user's picture, which is open), and **inventory-mobile** (it shows no tenant picture). A user's picture stays open (ADR 0056).

## Consequences

- `GET /tenants/{id}/picture` takes an optional token; the OpenAPI schema is unchanged in shape (the route's description changes), so `packages/api-client` regenerates by a few comment lines and the CLI models not at all.
- A test lists which picture and cover routes ask for what, so a route that gains or loses its token requirement changes it on purpose, and reads the private-repository answers against the other three.
- An invite link to a private repository shows its picture only after login. The page names the repository and its offer in words before, as ever.
- A public repository's picture and cover are as open as they were: the picture to anyone, the cover to anyone signed in.
