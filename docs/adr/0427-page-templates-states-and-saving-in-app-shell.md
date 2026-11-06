# 0427 - Page templates, states and saving in app-shell

Status: accepted, decided with the maintainer on 2026-11-06. Part of [RFC 0050](../rfcs/0050-the-web-interface.md); it implements [ADR 0412](0412-web-page-templates-and-saving.md) and [ADR 0413](0413-web-states-and-the-mascots.md) as UI-C ([#1014](https://github.com/ramsesoriginal/lorenzo/issues/1014)). It follows [ADR 0426](0426-the-web-shell-grows-in-app-shell-opt-in.md).

## Context

UI-A gave the brand its tokens and the save bar and skeleton styles, and UI-B the frame (header, palette, toasts, menus). What is left is what sits inside the frame: the seven page templates, the states (loading, empty, error, no access, offline), the mascot pages, and the two ways a page saves.

## Decision

- **The brand holds the look, `@lorenzo/app-shell` the behaviour.** Page parts are plain classes in `apps/brand` (`page-heading`, `form-section`, `state-block`, `page-state`, `home-grid`, `home-block`), listed in `web-classes.json` so the class-clash test protects the other apps. `page-head` was taken by Maps, Sessions and Social, hence `page-heading`.
- **The template is chosen by the page.** `AppPage` takes `template` (list-detail, reading, form, editor, board, workspace, home); it sets the container class (`shell-page`, `--reading`, `--form`, `--wide`) and nothing else. Without it nothing changes.
- **States are built by app-shell**, not by each app: a region state is a `state-block` of a kind (empty first time, empty after a search, loading slow, error, partly loaded, conflict, offline) with the words of ADR 0413, and a page state names its mascot image by id. An image that is not there yet leaves a dashed placeholder, and the words carry the meaning. No state counts what a person cannot see.
- **Reads retry, writes do not.** A failed read retries with a short backoff and says so; after it gives up a "Try again" button stays. A write is never retried automatically.
- **Saving is a choice the page makes.** An explicit save bar controller for forms with irreversible effects (it rewrites its buttons only when the number of changes changes); an autosave indicator (saving, saved, kept on this device) for writing; a field that is reversible saves as it changes with an Undo toast (already in the shell). Both feed the `unsent()` guard so signing out says plainly what is only on the device.

## Consequences

- Delivered as stacked parts: the brand's page parts, then templates, states and mascots, then saving and retry.
- The mascot images are the illustrators' (`ui_<id>.png`, [mascot-images.md](../design/web/mascot-images.md)); they are served from `<brandingUrl>/mascots/`, and until they are delivered the placeholders show.
- Each app adopts the templates and states when it moves over (UI-D to UI-G).
