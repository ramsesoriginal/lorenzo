# 0385 - Studio's profile editor and the cover controls

Status: accepted. Slice T5 of [RFC 0036](../rfcs/0036-repository-tooling.md) §4, tracked in #972; the screens for the profile of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §2. Builds on [ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md) (the profile and its routes), [ADR 0290](0290-the-flips-as-routes-and-the-visibility-switch.md) (the visibility card and the Make public dialog), [ADR 0292](0292-discover-the-listing-and-the-storefront.md) (what Discover shows), [ADR 0300](0300-authentication-on-a-private-repositorys-picture.md) (a cover is fetched with the token) and [ADR 0384](0384-deprecating-a-repository.md) (the shape of a Studio card). The choices marked *default* were not put to the maintainer; each is listed as a question at the end.

## Context

An Owner could write a summary only inside the Make public dialog. Nothing in the hub edited the licence, credits, tags, game system or languages, or set, replaced or removed a cover, though the API has had all of it since ADR 0213. This slice is the hub half: no API change.

## Decision

### Where it is, and who may change it

- **A Profile tab** on a repository's page in Studio, after Overview, as RFC 0036 §4 lists it. Every member reads it (the API's `GET .../profile` and `GET .../profile/cover` answer any member); a member who is not an Owner reads it **read-only**: no inputs and no buttons, "Only an Owner can change this.", the cover, and what people will see.
- **Only an Owner may change it, which is what the API does** (`PATCH` and the cover's `PUT` and `DELETE` are the Owner check of the other repository routes, an Organizer gets `403 repository-management-forbidden`). The screen mirrors that exactly: an Organizer and an Author get the read-only page. If RFC 0040 lets an Author or Organizer edit it, the API changes and `mayEditProfile` in `lib/profileEditor.ts` is the one place the screen follows.
- No tab is shown for a library: a library has no profile (ADR 0213), and this slice adds none.

### The form, field by field

One form and one **Save**, sent as **one `PATCH` of what changed** (`patchOf`: only the fields that differ from what the API has, so a field another Owner changed meanwhile is not overwritten; `null` clears the licence and the game system, `[]` a list). The API's answer, which is the profile as it kept it, is drawn back, so the person sees the normalised form. "Saved." confirms. **Revert** goes back to what the API has. Save and Revert are off while nothing differs. The profile has no `ETag`/`If-Match` (the route does not take one), so there is none to send; a second Owner's change to another field is not lost, and to the same field the last save wins (a question below).

The rules mirror `schemas/repository_profiles.py` so that the screen tells a person before the request what the API would only refuse after it (`lib/profileEditor.ts`, one place with the limits). The wording of each refusal is the API's own, so the screen and the API say the same thing.

| Field | What the screen does |
| --- | --- |
| **Summary** | A text area with the help of the Make public dialog (`SUMMARY_HELP`) and a count against 280 as the API keeps it, on one line. Empty is allowed here: only making it public asks for one. |
| **Licence** | A choice: "No licence stated" (the empty state, with a line that says it is not a licence), a short list (CC0 1.0, CC BY 4.0, CC BY-SA 4.0, CC BY-NC 4.0, CC BY-NC-SA 4.0, ORC License, OGL 1.0a, All rights reserved) and "Other…" with a free name of up to 80 characters. A listed Creative Commons licence brings its usual link, which can be changed or taken out. The link is optional, https only, and needs a licence (`LicenceIn` has a required label). Nothing in the list is a value the API refuses. |
| **Credits** | A list of name (required, 80), what they did (optional, 60) and a link (optional, https): add, edit, move up and down, remove, "N of 20 credits". It says it is not who published it. |
| **Tags** | Chips, added with Enter, a comma or "Add", several at once; shown back in the form the API keeps (lower case, whitespace made single, no repeats); up to 12 of 32 characters, "N of 12 tags"; a refusal says why next to the box. A chip is a button, so it is a full-size target on a phone. Suggestions (a `<datalist>`) are the tags of `GET /discover/facets` when it says `enabled`, never required. |
| **Game system** | One value of up to 40 characters, suggestions from the facets' systems. |
| **Languages** | Chips of language codes as the API takes them (`en`, `de`, `pt-br`), shown by name in the reader's own language with `Intl.DisplayNames` (`German (de)`), the code where the browser does not know it; up to 8. Suggestions are the facets' languages and a few common ones, never one already chosen. A name such as "German" is refused in the API's words; the person is not guessed at. |

**Refusals.** The screen checks first (an `http` link, a summary over 280, a thirteenth tag, a bad code) and sends nothing when it refuses, with the cursor in the first field at fault. What the API still refuses is read from its `422` (`errors[].loc` names the field: `licence.url`, `credits.1.url`, `tags`), shown in its words next to that field, and keeps nothing; a refusal that names no field (a `403`, a refusal a newer API adds) is one sentence above the buttons from the API's `detail`. Nothing the API said is rewritten.

**Unsaved changes.** Leaving the tab for another, choosing another repository in the list, and leaving the page each ask first ("You have unsaved changes to the profile. Leave without saving them?"; the page uses the browser's own prompt). A page that draws the repository again (after a publish, say) keeps what was typed. Text typed in a tag or language box and not added counts as unsaved, and is added by Save.

### What people will see

A small, read-only preview under the form, drawn **with Discover's own card**: `components/Discover/card.ts` fills the template that `DiscoverCard.astro` holds, and the list on `/discover` was changed to use the same function, so the preview is the card and not a copy of it. Under it, what the repository's own page adds: game system, languages, licence (or "No licence stated") and credits, with links shown only when they are https, as on the storefront (`rel="nofollow noopener"`). For an Owner it follows the form as it is typed; for a member it shows what is saved. The release, size and publisher are what a public repository adds, and the preview says so.

### The cover

A card on the tab, apart from Save: the cover as it is now (fetched with the token and shown from a blob, ADR 0300; `GET .../profile/cover`), "Choose a picture…" (or "Replace the picture…"), the type and size checked in the browser first (PNG, JPEG, WebP or GIF, up to 10 MB, the API's limits, said in words; the API still answers for itself), the chosen picture **shown before it is uploaded** with **Upload** and **Cancel**, and **Remove the cover** after a confirm ("Remove the cover? Discover will show the first letter of the repository’s name instead."). The API's refusal is shown in its words and the picture stays chosen. A repository with no cover says "No cover yet." and what Discover shows instead: the first letter of its name in the list, nothing on its own page. The cover is not counted by the quotas ([ADR 0298](0298-quotas-on-a-repository.md)), so nothing says anything of them.

**Why not `components/PictureUpload`.** That control uploads the moment a file is picked, is a 128-pixel square, removes without asking and has nothing to say for no picture; the cover is a wide strip that is looked at first and has Discover's stand-in to explain. Extending it to that would change two other call sites. What the two share is shared: the types and size (`lib/profilePicture.ts`), the status line, the fetch with the token (`lib/pictureFetch.ts`).

### One summary field

`components/Repository/summaryField.ts` binds a summary text area, its help and its count; the Make public dialog and the Profile tab both use it, on `SUMMARY_HELP`, `summaryCount` and `summaryProblem` of `lib/visibility.ts`. They cannot disagree. The dialog reads the saved profile when it opens, so it starts from what the tab saved; the dialog's `PUT .../public` writes the summary as before, and the tab reads it again afterwards.

### The readiness check

Under the visibility card on the Overview, for an Owner of a private repository that can be made public here: **"Before this can be public"**, a list of "It needs a summary…" (needed: `has_summary` of the flip check), "A cover is not required, but it is the first thing people see." (recommended: the profile's `has_cover`) and one line for each repository it is built on that is not public or has a release not taken (needed: **the texts and links of ADR 0290's `publicBlockers`, from the same flip check, not worked out again**), or "Everything it is built on is public and up to date." Each open item has a link that jumps to where it is fixed: "Write the summary" opens the Profile tab with the cursor in the field, "Add a cover" with the cursor on "Choose a picture…", a built-on repository the Owner owns goes to its page, and any other to the Built on tab. A done item says "Done". It is drawn again after the profile or the cover was saved. It **blocks nothing**: the flip's rules are the API's, and the dialog still lists what stands in the way.

### Phone

One column at 375 pixels, no sideways scroll, every button, field, select and link at least 44 pixels (tags and languages are buttons, external links in the preview carry `shelf-link`), as tests measure. The tab strip wraps as the brand's does.

### The words

Library, repository, release, Owner, entry, copy; never "tenant", "grant" or "subscription" ([ADR 0194](0194-user-facing-terminology.md)); a test checks the new screens. "Licence", "credits", "cover", "game system" and "tags" are the words of RFC 0038 §2 and Discover. No new word needed identity §14.3.

## Not in scope

- A profile for a library, and the Studio screens for it.
- Per-language summaries.
- Changing the list of licences centrally (it is a constant in `lib/profileEditor.ts`; a licence outside it is "Other…").
- Anything in the API: no route, field or limit changes; no `ETag`.
- The terms line, the publisher and the Report link (ADR 0299), view-as-subscriber (T6), the shared review extraction and the terminology sweep (#495).

## What the tests pin

- Unit: the https check and its words; the tag, language, licence and credit rules; the caps; the diff of what changed and the request it makes (only changed fields, the normalised form, `null` and `[]` to clear); what the API's `422` means next to which field; the language names in a given locale; the card and facts of the preview; the readiness list and who sees it.
- Real API: an Owner fills every field, saves it as one request, reloads and sees it, and Discover's list and the storefront show it; an `http` link, a long summary, a thirteenth tag and a bad code are refused in the screen and send nothing; the API's own refusals, reached by replacing the request on its way, are shown next to the field and keep nothing; the cover, its preview before upload, cancel, upload, replace, remove after a confirm, the API's refusal, and that a private repository's cover is fetched with the token and a public one is on its page; an Organizer and an Author read it read-only and the API refuses the Organizer; the readiness list, its links, and its update after Save; the Make public dialog starts from the saved summary with the same help and count; the unsaved-changes prompts; and 375 pixels.

## Questions for the maintainer

- Should an Organizer edit the profile? The API says no (an Owner only), and the screen follows it. RFC 0038 §2 assumed an Owner and left Authors to RFC 0040. *Default: Owner only.*
- Is the licence list right (CC0, four CC 4.0 licences, ORC, OGL 1.0a, All rights reserved), and should the ORC and OGL entries carry a usual link? *Default: the list above; links for the Creative Commons ones only, because they are the ones whose addresses are certain.*
- Should the profile take an `If-Match`, so that two Owners saving the same field do not silently overwrite each other? *Default: no; the screen sends only what changed.*

## Consequences

- The hub gains the profile editor with no API change; `packages/api-client` is untouched.
- `bindTabs` gained `select(index)` and an optional `canLeave` (additive); the other tabbed views behave as before.
- `languageLabel` takes an optional locale (default `en`, so Discover reads as before); the preview and the editor use the reader's.
