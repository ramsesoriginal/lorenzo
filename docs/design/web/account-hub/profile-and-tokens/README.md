# Account hub: profile and tokens

A fresh design of the two personal pages of the account hub: **Profile**, and **Access tokens** with **Connect a device**. The system is in [the web design](../../README.md): the shell, the templates, the states and the decisions D1 to D31. The account hub as a whole is decided ([AH1 to AH9](../README.md)); these two pages were drawn there as part of it, and are redesigned here on purpose. This page holds the brief, the questions and the decision log.

Status: the prototype is built and ready for review (decisions PT1 to PT6 are logged here).

## What the pages are for

- **Profile** is how a person appears to others: a picture (an uploaded one, else one computed from their verified email), a **nickname** (unique: the handle people are found by), a **display name** (not unique: the label shown in lists), **pronouns**, a **bio**, **languages**, and a **colour**. Who sees what is decided per field ([ADR 0060](../../../../adr/0060-user-profile-expansion.md)): the nickname, the display name and the colour reach other people (rosters, notifications); pronouns, bio and languages are private to the person and to admins. **Delete my account** sits here, and needs a signed-in session, never a token.
- **Access tokens** are how a program acts for a person: the command line first, a bot later ([ADR 0268](../../../../adr/0268-personal-access-tokens-api.md), [0269](../../../../adr/0269-personal-access-tokens-hub-and-cli.md)). A token **acts as its owner, whole**: no scopes. It has a name, the last four characters of its secret, a made date, a last-used time, and an expiry that is **Never** unless the owner chooses one. It is revocable. A person may hold at most 50. A token **manages nothing about tokens**: it cannot approve, deny, list or revoke, and cannot delete the account, so a leaked one ends when its owner revokes it from a signed-in session.
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

### PT1. Two pages, not tabs

Profile and Access tokens are two pages, each its own entry in the account menu ("Profile", "Access tokens and devices"), with no shared tab row.

### PT2. The profile shows who sees what, and saves as it goes

A form with a caption on each field saying who sees it, and a live "how others see you" card (a roster row and a notification line). Each field saves as it is changed and says so, with Undo.

### PT3. The colour is a set of swatches and a custom one

A small set of swatches, and "Custom…" for any `#RRGGBB`, with a check that it can be told from the surface it sits on, in light and dark. The name is what identifies a person; colour never carries meaning alone.

### PT4. Tokens read as rows with a state in words

Each token is a row with its state in words ("Never used", "Last used 3 weeks ago", "Expired", "Expires in 4 days") and a quiet note on one not used for a long time, so a forgotten one is noticed. Revoke is on each row. One plain sentence says that a token is a whole key. There is no grouping by device, since a token has a name and not a device.

### PT5. Connect a device is a page, and the tokens page embeds it

A page at `/device` is what the command line's link opens: what is asking, the code, a name for the token, when it stops (Never is the default), and Connect or Deny, with the sign-in and the way back for someone who is not signed in. Before anything else it says to approve only a code started by the person themselves. The Access tokens page embeds the same content under "Connect a device", with a box to type a code.

### PT6. The profile page is direction A

The "how others see you" card sits beside the form and stays in view as fields change. On a tablet and a phone it moves above the form.

## The directions (drawn; A chosen)

In `directions/`: the profile page in three layouts, the Access tokens page, and the Connect a device page in five states, on the shell with made-up data. The header's tab row is the shell's stand-in; in the hub the account button opens these pages (PT1) and there is no tab row between them. Run it:

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/account-hub/profile-and-tokens/directions/index.html
```

The controls bar switches the screen, the device page's state and the custom colour. Screens are in `directions/screens/` (10 images, at 1440).

| | A. Side card | B. Band | C. Inline |
| --- | --- | --- | --- |
| Where the "how others see you" card is | Beside the form, sticky, so it stays in view as fields change | A band across the top of the page, above the form | Inside the form, right after the Names it shows |
| Width | Wide: form and card side by side | One narrow column | One narrow column |
| On a phone | The card moves above the form | The same, a band | The same, inline |
| Best for | Seeing the effect of every change while editing | A quick glance, then a long form | A page that reads top to bottom as a story |
| Cost | A second column; at tablet width the card leaves the side | The card scrolls away when the form is long | The card interrupts the form, and sits far from the colour it also shows |

What is the same in all three: every field carries "Others see this" or "Only you and admins see this" with an icon and a word; fields save as they are changed and say so; the colour is five swatches and Custom…, which takes a hex and says whether it can be told from a light and a dark surface; Delete my account is at the foot and needs a signed-in session.

**Access tokens** is rows, each with its state in words (Last used today; Last used 3 weeks ago and Expires in 4 days; Not used for 120 days, with the note that it still works; Never used; Expired), the last four characters, and Revoke. A stale token is tinted and an expired one is struck through, and neither relies on colour. One callout says a token is a whole key. "Connect a device" is under it, with a box for the code.

**Connect a device** has five states: a code in the address (what is asking, the code and when it ends, a warning to approve only a code you started, a name, when it stops with Never first, what it can do, Connect and Deny); no code (a box to type it); a wrong code (one sentence); connected (a mascot slot, `device-connected`, and what happens next); and not signed in (sign in, and come back with the code kept).

What is not drawn yet: the phone, dark mode, the save feedback per field, the Undo, the revoke and delete dialogs, and the real picture picker. None of it has been through the checks.

## The prototype

The pages are the shell's own (`docs/design/web/prototype`, `pages.js`), so every app's account menu opens them and the account hub uses them; the hub's earlier copies are gone. `prototype/` here is the shell with a controls bar to reach each state; `prototype/build-review-copy.mjs OUT_DIR` writes a single page that runs without the repository.

### Profile (PT1, PT2, PT3, PT6)

- A form with a caption on every field: "Others see this" for the picture, nickname, display name and colour, and "Only you and admins see this" for pronouns, bio and languages. A sticky card shows a roster row and a notification line, and follows what is typed, including the initials, the name, the nickname and the colour.
- Each field saves when it is changed and says "Saved", with an Undo toast. A nickname that is taken, or not 2 to 30 letters, digits, dots, dashes or underscores, is refused next to the field and kept. The colour is five swatches and Custom…, which takes `#RRGGBB` and says whether it can be told from a light and a dark surface (3 to 1), or why not.
- Delete my account asks for the email to be typed, and says that it needs a signed-in session.

### Access tokens (PT4)

Rows with the name, the last four characters of the secret, a state in words ("Last used today", "Last used 3 weeks ago", "Expires in 4 days", "Not used for 120 days", "Never used", "Expired 3 weeks ago") and Revoke. A stale row is tinted and an expired one is struck through, and each also has its words and an icon. One callout says a token is a whole key. Revoke names the consequence and says it cannot be undone. A box takes a code from a device.

### Connect a device (PT5)

A page for what the command line's link opens, with the code in the address in any case, with or without the dash. It says what is asking, the code and when it ends, and, before anything else is asked, to approve only a code started by the person themselves. It takes a name (at most 80 characters, refused in words), when it stops (Never first), and Connect or Deny. Without a code it has a box to type it; a wrong code is one sentence; not signed in it says to sign in and that the code is kept; connected it shows the `device-connected` slot and what happens next.

### What it fakes

Nothing is saved or sent. The nickname that is taken is fixed ("mara"). A code is valid if it is eight letters. Signing in is a button that goes back to the page. The picture picker is a toast. There are no per-token details beyond the list.

### What was checked

148 scripted checks pass (Playwright, 1440 and 430), run on the shell, this prototype, the account hub and Social: every field's caption, the live card, saving and Undo, the two refused nicknames, the colour and its three readability messages, delete; the five token states, the whole-key sentence, revoke with its consequence, the empty list, a wrong code, a code in any case, the device page's warning and its default, the name refusal, connecting, Deny, no code, a wrong code, not signed in; and on a phone, no horizontal scroll, the card above the form and 44 px targets. axe-core finds no violations on 16 states at 1440 and 430, light and dark (64 runs). There are no console errors.

### What was not checked

A screen reader, a real phone, colour-blindness simulation, Safari and Firefox. The page's request for no referrer and the real sign-in round trip are not drawn.

### Findings

- A save bar rewrote its own buttons on every change, so a click on Save that followed an edit blurred the field and lost the click. The shell's, the hub's and now no profile save bar do that; fields save as they change here.
- The shell used a helper that the other prototypes define for themselves; the pages now carry their own.
- The default custom colour was a purple that could not be told from a dark surface, which the check said; it is a blue that works on both.

### Screens

In `screens/` (15 images): the profile, refused, and with the custom colour; the tokens and revoke; the device page with a code, with none, with a wrong one, not signed in and connected; dark; and the phone.

## Open questions

None are open.
