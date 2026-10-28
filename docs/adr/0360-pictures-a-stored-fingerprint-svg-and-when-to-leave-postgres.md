# 0360 - Pictures: a stored fingerprint, SVG, and when to leave Postgres

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 9. Extends
[ADR 0017](0017-information-and-payloads.md) (bytes live in Postgres) and
[ADR 0237](0237-api-pictures-and-information-order.md) (pictures on information) for the layers of
[ADR 0361](0361-map-layers.md).

## Decision

**A fingerprint is stored with every picture.** `payload_picture.sha256` is a generated, stored
column, `sha256(data)`, so no write path can leave it stale or forget it, and a migration gives every
existing picture its hash. It is read by the layers (ADR 0361) to say that a picture is not the one a
layer was set up for. It is never accepted from a client.

**SVG joins the pictures an entry may hold.** `image/svg+xml` is accepted by the upload of a picture
payload and of a main picture, beside png, jpeg, webp and gif, and by nothing else: profile and cover
pictures keep the old list. The declared type is trusted as for every picture here (ADR 0017), which is
why an SVG is also read: **one lint, reject and never rewrite** (`lorenzo_api/svg_lint.py`, pure), run
by the upload and by the repository copy, accepts a document only when

- it is well-formed XML with `svg` in the SVG namespace as its root, has no document type declaration
  or entity, is at most 64 levels deep and holds at most 50,000 elements;
- every element is of a fixed list of drawing elements (`svg`, `g`, `defs`, `title`, `desc`, `path`,
  `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `text`, `tspan`, `use`, `image`,
  `linearGradient`, `radialGradient`, `stop`, `clipPath`, `mask`, `pattern`, `style`), so `script`,
  `foreignObject`, `a`, `iframe`, `animate`, `set` and anything unknown are refused;
- no attribute is an event handler (`on...`), no `href` or `xlink:href` points anywhere but at a
  fragment of the document (`#id`) or at a `data:image/png`, `jpeg`, `gif` or `webp` URL, and no
  attribute value or `style` text holds `javascript:`, `@import`, an `expression(` or a `url(` that is
  not of a fragment.

A refused picture is a 422 with one sentence; the lint changes nothing in what it accepts. A copy that
meets an SVG the lint now refuses drops that picture with a reason, as for any invalid row.

**How an SVG is served and drawn.** `GET /payloads/{id}/content` stays the only route, bearer-gated and
checked against the information's audience. Every picture now carries `X-Content-Type-Options:
nosniff`; an SVG also carries its stored type as the only `Content-Type`, `Content-Security-Policy:
default-src 'none'; sandbox` and `Content-Disposition: attachment`, so that opening it as a page runs
nothing and shows nothing. A client draws an SVG only as an image from a `data:` URL it made itself,
never from a `blob:` URL a page can reach, never inline and never by reading an element's id: a hotspot
is always one of our own placements over the picture.

**Limits stay as they are.** 10 MB a picture (`picture_max_bytes`), and a repository's pictures count
against its 20 MB through the quota that already watches `payload_picture`; a copy re-stores every
byte. A layer adds no bytes of its own.

**When to leave Postgres** (nothing is built; this only says when to decide again). The decision is
opened by the first of these to be true in production, measured by an operator and recorded in a new
ADR: the pictures hold more than **2 GiB** in all; the 95th percentile of `GET /payloads/{id}/content`
is over **400 ms** for two weeks running; or a restore of the database from its backup takes over **30
minutes**. The numbers are first values, loosened or tightened by ADR after measurement.

## Validation and delivery

Lint: a golden list of documents accepted and refused (each refused rule once, nested and encoded
forms of `javascript:`, an entity, a deep document, an oversize one). API: the stored hash of a new,
replaced and copied picture, the SVG upload and its refusals, the headers of a picture and of an SVG,
a main picture as an SVG, a profile picture still refusing it, and a copy dropping a refused SVG.

## Excluded

Rewriting or sanitising an SVG, inline SVG, SVG element ids as targets, raster conversion, a picture
store outside Postgres, and a hash a client can supply.
