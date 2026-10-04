# 0180 - account-hub: one-click setup

Status: accepted, decided with the maintainer on 2026-10-04. Uses [ADR 0175](0175-me-says-what-you-may-create.md) (who may set up) and [ADR 0177](0177-gm-invite-links.md) (the GM link). It is the v1.0 row "1-click setup"; no RFC came before it, the design having been settled with the maintainer in conversation.

## Context

Starting a table in account-hub today is six separate acts: create a library on `/tenants`, create a campaign there, find that campaign's invite panel, make a link, copy it, and (to name a GM) look up a user by email or nickname. Each is a form on a page that was built for administration, and each has its own failure.

## Decision

A page of its own, **`/setup`**, "Set up a table", turns that into one short form and one result.

### Who sees it

Only an account whose `GET /me` says `capabilities.create_tenant` ([ADR 0175](0175-me-says-what-you-may-create.md)). Others get one sentence saying creating a library is not open to their account yet. It is linked from the home page and from the empty states of `/tenants` and `/campaigns`.

### The form

- **Library name** (required). A library holds a group's campaigns and characters; one sentence says so.
- **Campaign name** and **game system** (required; the API requires both). The slugs are derived from the names, by a pure, tested helper; a slug clash is reported as such.
- **Who runs the campaign**, one of:
  - **I do** (the default): the creator is made a GM.
  - **Someone I can find**: by email or nickname, with the picker `/tenants` already uses; they are made a GM now.
  - **Someone I'll send a link to**: a **single-use GM link** ([ADR 0177](0177-gm-invite-links.md)), for someone who has an account or doesn't.
- **How long the player link lasts**: a preset, a week by default. Its uses are not limited.

### What it does

A chain of the calls that already exist, in order, shown as it goes:

1. `POST /tenants`: the library (the creator becomes its owner).
2. `POST .../campaigns`: the campaign.
3. The GM: `PUT .../gms/{user}` for the creator or the person found, or `POST .../invites` with `role: "gm"` for the link.
4. `POST .../invites`: the player link.

### The result

One screen, with both links where there are two. Each is shown once, with a Copy button ([ADR 0171](0171-account-hub-campaign-invite-links.md)'s panel does the same), and "Done" clears them from the page. They are `/join/#<token>` addresses, so the token stays out of every log and referrer. Beside them: the campaign's name, and links on to the library and the campaign on `/tenants`.

### When a step fails

The chain stops at the step that failed, says which and why in the words of [ADR 0170](0170-account-hub-readable-errors-self-service-exits-and-admin-basics.md)'s errors, and offers **Try again**, which resumes from that step: what was made is kept in memory for the page's life. Reloading loses those handles, but nothing is wrong with what exists: a library with no campaign, or a campaign with no link, is an ordinary state that `/tenants` already shows and can finish.

## Alternatives considered

- **One endpoint that does it all, atomically.** A new API surface and an ADR, to avoid a failure the chain already handles by stopping and saying so. If the chain proves too fragile in use, this is the follow-up.
- **Set up on first login.** Creating a tenant as a side effect of logging in, for an account that may not even hold the creator role.
- **A wizard of several screens.** More clicks, which is the thing this exists to remove.
- **Reuse the create forms on `/tenants`.** They are built for adding to a library that exists.

## Not in scope

- **Subscribing the new library to repositories**, an optional wish of the maintainer. It needs the subscribe screens (a copy plan and its choices) that do not exist yet; it waits for the v1.0 row "Publish, subscribe, update screens", and `/setup` leaves room for a step.
- **More than one campaign, or more than one GM,** at setup: `/tenants` and the invite panel do that.
- **Naming a tenant-wide role** (the v1.0 "tenant-role invite links").

## Consequences

- **Client-only**, on top of the three API changes it needs ([ADR 0175](0175-me-says-what-you-may-create.md), [0176](0176-a-campaigns-people-come-with-their-names.md), [0177](0177-gm-invite-links.md)). Unit tests cover the slug helper and the step plan; a real-browser spec runs the whole chain against the real API for each of the three "who runs it" choices, and a failure and its retry; a logged-out smoke spec covers the page.
- Copy follows [identity §14](../brand/identity.md): library, campaign, no "tenant".
- Reloading mid-setup is not resumable by the page itself; the result is nonetheless always recoverable from `/tenants`.
