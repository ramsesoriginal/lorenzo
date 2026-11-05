# Account hub: profile and tokens

A fresh design of the two personal pages of the account hub: **Profile**, and **Access tokens** with **Connect a device**. The system is in [the web design](../../README.md): the shell, the templates, the states and the decisions D1 to D31. The account hub as a whole is decided ([AH1 to AH9](../README.md)); these two pages were drawn there as part of it, and are redesigned here on purpose. This page holds the brief, the questions and the decision log.

Status: the brief and its questions. Nothing is decided yet.

## What the pages are for

- **Profile** is how a person appears to others: a picture (an uploaded one, else one computed from their verified email), a **nickname** (unique: the handle people are found by), a **display name** (not unique: the label shown in lists), **pronouns**, a **bio**, **languages**, and a **colour**. Who sees what is decided per field ([ADR 0060](../../../adr/0060-user-profile-expansion.md)): the nickname, the display name and the colour reach other people (rosters, notifications); pronouns, bio and languages are private to the person and to admins. **Delete my account** sits here, and needs a signed-in session, never a token.
- **Access tokens** are how a program acts for a person: the command line first, a bot later ([ADR 0268](../../../adr/0268-personal-access-tokens-api.md), [0269](../../../adr/0269-personal-access-tokens-hub-and-cli.md)). A token **acts as its owner, whole**: no scopes. It has a name, the last four characters of its secret, a made date, a last-used time, and an expiry that is **Never** unless the owner chooses one. It is revocable. A person may hold at most 50. A token **manages nothing about tokens**: it cannot approve, deny, list or revoke, and cannot delete the account, so a leaked one ends when its owner revokes it from a signed-in session.
- **Connect a device** is the flow that makes one. The device asks for a code and shows eight letters (`ABCD-EFGH`: consonants only, so no words). The person opens the hub at `/device` (the CLI prints an address with the code in it, or the plain address to type it), sees what is asking, names the token, chooses when it stops (Never, 30 days, 90 days, a year), and connects or denies. A code lives ten minutes. The secret is shown to the device once and **never in the hub**.

Roles in play: every signed-in person, for their own account only. Nobody sees another person's tokens.

## The jobs

| Who | The job | Needs from the data |
| --- | --- | --- |
| Anyone | Change how I appear: picture, names, pronouns, languages, colour | the profile; who sees which field |
| Anyone | See what others see of me | the roster fields |
| Anyone | Connect the command line, a script or a bot | the device code, the request |
| Anyone, arriving from a link | Approve a code the CLI printed, possibly before signing in | the code in the address, the sign-in and the way back |
| Anyone | Find a token I forgot and revoke it | the list, last used, expiry |
| Anyone who lost a laptop | End every token on it at once | the list |
| Anyone | Delete my account | a signed-in session |

## What stays true, whatever it looks like

- **A secret is shown once, and not here.** The hub never shows a token's secret; it shows the last four characters to tell two tokens apart.
- **A token is a whole key, and the page says so plainly,** where the person decides (when connecting) and where they look (the list), without alarm and without scopes that do not exist.
- **Only approve a code you started.** A device code can be sent to someone by another person; the approval page says what is asking and to approve only what they started themselves.
- **A wrong or used-up code gets one sentence:** that it is not valid or has ended, and that codes last ten minutes. No difference between wrong, used and expired (D27).
- **The page with a live code in its address asks for no referrer** and says nothing the address could leak.
- **Visibility is told per field, in words,** with a neutral badge and an icon, never a colour. "Others see this" and "Only you and admins see this".
- **Revoke and delete name their consequence** and ask first; the biggest asks for a name typed (D26). A revoked token stops at once and cannot be undone: connect the device again.
- **A refusal is shown as the API gave it,** next to the field, and the draft is kept. Nothing says "saved" that is not.
- **Words follow identity §14.3:** "device", "personal access token" in full where it is first met, "library"; never "tenant" or "OAuth".
- **The API decides every permission,** and a token-authenticated request cannot reach these controls at all.

## What the old design decided

Named from the earlier account hub design and its prototype, so each is decided again on purpose. Nothing is taken from the current screens.

| Old decision | What it was | Asked in |
| --- | --- | --- |
| One area, two tabs | "Your account" with Profile and Access tokens as tabs, behind the account button | Q1 |
| Tokens on the profile page | The ADR puts "Personal access tokens" as a section of `/profile`; the prototype made it a tab | Q1 |
| A save bar for the profile | Edits are collected and saved together | Q2 |
| Five colour swatches | A small set; the API takes any `#RRGGBB` | Q3 |
| A table of tokens | Name, made, last used, expires, Revoke | Q4 |
| Connect a device inside Tokens | A code box and an approval card on the tokens page | Q5 |
| Delete my account at the foot of Profile | Type your email to confirm | kept |
| Notifications behind the account button | A bell and a page | decided (D27) |

## Already decided

- **The shell** (D12 to D31): the account menu (Profile, Notifications, Libraries and people, Access tokens and devices, Appearance, Keyboard shortcuts, Sign out), the status bar, overlays, states.
- **Saving by template** (D21): entry fields autosave and say so; forms with irreversible effects use the save bar.
- **Confirmation by weight** (D26): Undo for what can be reversed; a named consequence for revoke; the name typed for delete.
- **A secret shown once** (D26 and the hub's rule), **a dead link says one thing** (D27).
- **Phone:** one breakpoint at 720px, 44px targets, the page in one column, a table becoming a list.
- **Appearance** is a dialog from the account menu and is not redrawn here.

## Questions

**1. How are Profile and Tokens arranged?**

- **A. One "Your account" page with tabs:** Profile, Access tokens. The account menu opens either. This is the prototype.
- **B. Two pages,** each its own entry in the account menu ("Profile", "Access tokens and devices"), with no shared tab row.
- **C. One long page** with Profile, then Access tokens, as in ADR 0269's wording of a section on `/profile`.

My recommendation: B. The two share nothing but a person; they are reached for different reasons and the account menu already names them apart. A tab row adds a place to go for no gain, and a long page buries the tokens a person came to revoke.

**2. How does Profile show who sees what, and how does it save?**

- **A. A form,** each field with a caption saying who sees it, saved with the save bar.
- **B. A form with a live "how others see you" card** (picture, display name, nickname, colour as a roster row), autosaving each field with an Undo toast.
- **C. Both,** with the preview beside the form and each field saving as it is changed.

My recommendation: C. The split between public and private fields is the thing a person cannot tell from the field names; a preview of the roster row shows it. Profile edits are all reversible, so each saves as it goes, as Writing and Beings do, and says so.

**3. How is the colour chosen?**

- **A. A small set of swatches** that are safe on every surface.
- **B. Any colour,** by hex or a picker.
- **C. Swatches, and "Custom…"** for any hex, with a check that it can be told from the surface it sits on.

My recommendation: C. The API takes any `#RRGGBB`, so a fixed set is a choice the data does not need; but a free pick can be unreadable, so the custom one is checked, and the name stays what identifies a person (colour never carries meaning alone).

**4. How do the tokens read?**

- **A. A table:** name, made, last used, expires, Revoke.
- **B. Rows with a state in words:** "Never used", "Last used 3 weeks ago", "Expired", "Expires in 4 days", and a quiet note on a token that has not been used for a long time, so a forgotten one is noticed. Revoke on each.
- **C. B, grouped by device**, with a count, and "Revoke all" behind a confirmation for a lost laptop.

My recommendation: B, with C's group revoke only if the data can say which tokens share a device (it cannot today: a token has a name, not a device). So B, and a plain sentence that a token is a whole key.

**5. Where is "Connect a device", and what does the approval say?**

- **A. A page of its own at `/device`,** what the CLI's link opens: the request, the name, the expiry, Connect or Deny; the same content is embedded in Access tokens as "Connect a device" with a code box.
- **B. A dialog over Access tokens** only.
- **C. Only on the Access tokens page,** with the code box.

My recommendation: A. A link from a terminal has to land somewhere that can sign a person in and bring them back with the code; it must also say, before anything else, what is asking and to approve only what they started. The tokens page embeds the same component.

Say which, or say what is missing from this brief. No answer means "as recommended".

## Decision log

Nothing is decided here yet.
