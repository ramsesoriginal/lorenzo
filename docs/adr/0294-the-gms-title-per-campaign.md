# 0294 - The GM's title, per campaign

Status: accepted, decided with the maintainer on 2026-10-07 in [RFC 0040](../rfcs/0040-authors-and-invites.md) §4 ("its own small ADR"); the names, length and characters below are settled here. Tracked in #733. Reserved by [ADR 0194](0194-user-facing-terminology.md) ("GM, with a title a campaign may set for itself").

## Context

A game master is called something else at many tables: DM, Storyteller, Narrator, Master. Every surface that says "GM" says it the same way, whatever the table calls them. The RFC fixed what could be fixed so this record can be short: the title is per campaign, set by its managers, a singular and a plural, "GM" and "GMs" when unset, a label and not a role, additive in the API.

## Decision

### The two fields

`campaign.gm_title` and `campaign.gm_title_plural`, text, both null while the campaign keeps the default. Both are written through the existing `PATCH /tenants/{id}/campaigns/{id}`, by whoever may manage the campaign (a GM of it or an admin, as for its other fields), and are part of its `If-Match` and `campaign.updated` log line as field names, never values.

- **Written together.** Either both are given, or both are empty. A title without its plural, or the reverse, is `422`: the plural is not always the singular with an `s` ("Master", "Masters" would be fine, "Mistress of Ceremonies" is not), so no plural is derived.
- **Empty clears.** `""` (after trimming) sets both back to the default. Omitting both leaves them alone.
- **Plain text, 1 to 30 characters each** after trimming whitespace at both ends: letters, digits, spaces, and the punctuation of a name (`'`, `-`, `.`, `,`, `&`, `/`, parentheses). Not a control character, not a line break, nothing that reads as markup (`<`, `>`, `` ` ``, `*`, `_`, `[`, `]`, `~`, `|`, `\`), so a client may put it into a sentence in HTML, in Markdown or in a Discord message without escaping rules of its own. Anything else is `422 campaign-gm-title-invalid`.
- **Spelled as written.** The API never changes its case. Strings are written so a title reads right at the start of a sentence and in the middle of one ("Storyteller only", "ask the Storyteller"); nothing is lower-cased by a client.

### What the API says

`CampaignOut` and `CampaignSummaryOut` carry **`gm_title` and `gm_title_plural`, always set**: the campaign's own or `"GM"` and `"GMs"`. A client never defaults them itself, so the default is in one place, and the campaign settings screen shows a title equal to the default as the unset state. No client has to ask separately.

### What reads the title, and what does not

- **Reads it:** a text a person reads about **one campaign's** things: the campaign page and its settings, its characters, items and beings, the notes of its characters, a drop of the loot bot that names it, the API's notification about it ("A new Storyteller joined *Name*"). The audience name "GM only" follows the same rule: it reads "*Title* only" where the text belongs to a campaign's character, being or item instance, whose campaign is known.
- **Several campaigns in play.** A character, being or list that spans campaigns, or a bot reply about "a campaign you GM", uses the title only when every campaign involved has the same one; otherwise it says "GM" and "GMs". One small function per client decides this from the campaigns it has, so no surface decides alone.
- **Does not:** anything with no one campaign in it: a library's catalog and the entries of a repository ("GM only" there is the audience that a copy brings to a library whose campaigns each name their own GM), Studio and Bench, the activity log's field names, the CLI and the documentation. These say "GM", the word of the API.
- **Not changed:** every identifier and route (`/gms`, `GmOut`, the `gm` role of an invite link, `campaign.gm` rows), the role, and what a GM may do. A problem type's fixed `title` (the one line of `application/problem+json`, `Only a GM can do that`) stays fixed per type, and so do the details of the item routes, whose owner may belong to several campaigns or to none: they say "GM".
- **First use.** The RFC asks for "game master" to be spelled out on first use in a surface. A surface that has room for it writes "game master (DM)" once; the API sends only the two fields.

### Strings become templates

A client that says "GM" for a campaign takes the title from the campaign it already has (it is in the list rows as well as the page), through one small function per client that returns the singular or plural (and the audience text), so no surface keeps the word in a literal. Wording that needs an article is rewritten so it does not: "a GM" would turn into "a Narrator" or "an Illusionist", so a text says "the Storyteller of this campaign" or "*Title* only" instead. A test per client fails on a literal "GM" in a campaign's surface.

## What the tests pin

- The default is `"GM"` and `"GMs"` on every campaign read, in the list and on the page; setting both reads back; setting one is `422`; `""` returns both to the default.
- A title with a line break, markup, a control character or more than 30 characters is `422`; one with an apostrophe or a space inside is accepted as given.
- Only a manager of the campaign sets it; `If-Match` applies; the log carries the field names only.
- The invite notification reads the title; the library-wide "A GM matched what you wrote" and the item-instance details do not.
- Clients: no literal GM in a campaign's surface, the plural where several are meant, "GM" in a library or a repository.

## Not in scope

- A title for a library or a repository (they have no campaign).
- Gender and other inflections, a title per language, and a translated "game master" (RFC 0040 defers them).
- Renaming the role in API routes or invite links.

## Consequences

- A table calls its game master what it wants, and every surface of that campaign agrees.
- The default lives in the API in one place; no client holds a list of titles.
- A library with several campaigns that each name their GM differently says "GM" where no one campaign is in play, which is the word the repository, the catalog and the API already share.
- One migration: two nullable columns on `campaign`.
