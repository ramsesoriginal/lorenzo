# 0418 - Profile, access tokens and connecting a device

Status: accepted, decided with the maintainer on 2026-11-05. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web/account-hub/profile-and-tokens](../design/web/account-hub/profile-and-tokens/README.md), PT1 to PT6, D32. Follows [ADR 0060](0060-user-profile-expansion.md), [0268](0268-personal-access-tokens-api.md) and [0269](0269-personal-access-tokens-hub-and-cli.md).

## Context

ADR 0269 put "Personal access tokens" on the profile page and a "Connect a device" page at `/device`. The maintainer asked for these pages to be designed again as personal pages, and for them to be reachable from every app.

## Decision

- **Two pages, not tabs** (PT1): Profile and Access tokens, each its own entry in the account menu; the shell carries them so every app's menu opens them.
- **Profile** (PT2, PT3, PT6): a form with a caption on every field saying who sees it ("Others see this" for the picture, nickname, display name and colour; "Only you and admins see this" for pronouns, bio and languages), and a sticky "how others see you" card (a roster row and a notification line) that follows what is typed; on a tablet and a phone the card moves above the form. Each field saves as it is changed and says so, with an Undo. The colour is five swatches and **Custom…** for any `#RRGGBB`, with a check that it can be told from a light and a dark surface (3 to 1). Delete my account asks for the email to be typed and says it needs a signed-in session.
- **Access tokens** (PT4): rows with the name, the last four characters, and a state in words ("Last used today", "Not used for 120 days", "Never used", "Expires in 4 days", "Expired 3 weeks ago") and Revoke. A stale row is tinted and an expired one struck through, and each also has its words and an icon. One callout says a token is a whole key. Revoke names its consequence and says it cannot be undone. There is no grouping by device, since a token has a name and not a device.
- **Connect a device** (PT5): a page for what the command line's link opens, with the code in the address in any case, with or without the dash. It says what is asking, the code and when it ends, and before asking anything, to approve only a code the person started. It takes a name (at most 80 characters), when it stops (Never first, as in ADR 0269), and Connect or Deny. Without a code it has a box; a wrong, used or expired code is one sentence; not signed in it says to sign in and keeps the code; connected it says what happens next. The tokens page embeds the same content with a box for a code.
- **The page with a live code in its address asks for no referrer** (ADR 0269).

## Consequences

- The secret is never shown in the hub; the last four characters tell two tokens apart.
- A token cannot reach these controls (ADR 0268); the design says so where the person decides.
- The picture upload, the nickname's uniqueness refusal and the real sign-in round trip are the API's and the identity provider's; the design only shows their words.
