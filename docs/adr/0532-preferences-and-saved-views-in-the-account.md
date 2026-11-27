# 0532 - Preferences and saved views in the account

Status: accepted and built, 2026-11-27, asked for by the maintainer as slice A3 of UI-H's API work ([ADR 0528](0528-ui-h-retiring-the-old-frame-and-auditing-the-apps.md), H3). It is the "API surface for a person's preferences" that [ADR 0411](0411-web-widths-containers-density-and-type.md) and the account hub's follow-ups (#1129, D22) said did not exist, and the home for the saved views the design asks for.

## Context

The shell keeps a person's appearance (theme, density, motion) in each browser, so signing in on another device starts again from the defaults; and the lists with filters (Relationships, the Events list, a library's beings) forget what a person set them to. Both are per person, and not per tenant, in the one case; per person and per library in the other.

## Decision

- **Appearance in the account.** `app_user.preferences` (`jsonb`, `{}` by default) holds `{theme: system|light|dark, density: comfortable|compact, motion: normal|reduced}`, each optional (a part that is absent is the device's own choice). `GET /me/preferences` reads it and `PUT /me/preferences` replaces it whole (a part left out is cleared; an unknown word or name is a 422). There is no `If-Match`: they are one person's own, as [ADR 0054](0054-user-identity-email-and-nickname.md) says of the self-editable profile, and the last write is the one they meant. It belongs to the user, and so, like `app_user` itself, it has no `tenant_id` and no tenant row-level security.
- **Saved views.** A table `saved_view` (`tenant_id`, `user_id`, `app`, `list`, `name`, `query`) keeps what a person set a list to, by name, in one library. It has a `tenant_id` and the same `FORCE ROW LEVEL SECURITY` policy as every tenant table, and every read and write also filters on the caller's `user_id`: a view is read by the person who made it and by no one else (an administrator included; the log of what a person saved is not what a library keeps). It is not content: a repository never carries it, and a copy leaves it out.
  - `GET /tenants/{t}/saved-views?app=&list=` lists the caller's own, by app, list and name.
  - `POST /tenants/{t}/saved-views` keeps a view under a name. The same name for the same list replaces its `query` (and answers `201` with the same id), so "save" is one gesture.
  - `PATCH …/{id}` renames or replaces the query; `DELETE …/{id}` removes it; another person's id is a 404.
  - **Bounds.** A query is an object of at most 4,000 bytes; a person keeps at most 50 views in a library (the 51st is a 422; replacing one that is there is not adding one). `app` and `list` are short lowercase words naming the page, so a view means something only to the page that made it, which reads and writes it as it likes.
- **What the shell and the pages do with it** is H4: the shell reads `/me/preferences` once signed in, applies it before the device's own where it names a part, and writes it when a person changes Appearance while signed in; the device's choice stays the fallback when signed out or offline. A list with filters offers "Save this view" and its saved views beside its filters.

## Consequences

- One migration (`c05320000001`): a column and a table. `saved_view` is classified in `copyable_tables.py` as not content, so the table-classification tests pass and a copy writes none.
- A person's appearance follows them between devices; their saved views follow them between devices within a library.
- Tests: `tests/test_preferences.py` (the preferences are one's own and replace whole; saved views are kept per person and library, replaced by name, renamed, deleted, bounded in size and number, and not readable by anyone else).
