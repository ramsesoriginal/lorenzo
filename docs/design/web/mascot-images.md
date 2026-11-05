# Mascot images for the web interfaces

The images the web apps need from the mascots, Lorenzo and Catileo, as a list an illustrator can work from. The character rules are in [Lorenzo's character bible](../../brand/lorenzo-character-bible.md) and [Catileo's](../../brand/catileo-character-bible.md); the usage rules are [identity §9](../../brand/identity.md#9-mascot-and-illustration-system). This page says which images, where they are used and what each shows. It does not change those documents.

Placements are in the web design in this directory; the words beside each image are working copy that follows [identity §14](../../brand/identity.md#14-voice-and-writing) and are settled in each app's design.

## Rules that apply to every image

- **Level L4, spot illustration** (bible §17): bust or half-body, one shadow, up to two props, a simple motif behind. Not a hero illustration and not an icon.
- **Identity anchors stay** (bible §17.1): asymmetric dark hair with the blue sweep, blue eyes, the gold compass or spark motif, an asymmetric pose. No chibi proportions.
- **Lorenzo** is a person who keeps worlds, not a fantasy wizard. They use "they". Expressions come from the bible's library by name.
- **Catileo** stays a cat (bible §24): no standing upright, no human hand gestures, no reading, typing or holding tools. Expressions are the cat expressions of bible §13; no human eyebrows.
- **Genre mixing** (identity §9.4): props and motifs come from different settings (an orbital station, an apartment block, a detective file, a castle, an alien moon, a family tree, an ordinary city map). No image reads as fantasy by default.
- **Gold is punctuation.** The spark may appear as a prop. It does not glow, because a glow means "canonical" in the interface.
- **No text in the art.** No baked words, no signs or labels in any language.
- **No background and no scenery behind dense data.** The motif sits close to the character.

## Delivery

| What | Value |
| --- | --- |
| Format | PNG with a transparent background |
| Master | 2400 × 2400 px, square, the subject inside the central 80% |
| Web exports | 1280 px and 640 px, optimised, named `ui_<id>.png`, for example `ui_empty-entries.png` |
| Displayed at | 240 to 320 CSS px on desktop, about 200 px on a phone; the first-run images at 360 px |
| Backgrounds | Must read on Paper (`#FBFAF7`) and on Ink (`#08131F`). One version with a thin light keyline, as the emblem has, is preferred. If that is not possible, a second version for dark is delivered. |
| Alt text | Not part of the art. Each entry below says what the image shows; the interface writes the alt text (identity §15.3). |

## The list

Priority 1 is what the first builds need. Priority 2 follows. Priority 3 is optional.

### Welcome and empty

| ID | Priority | Where | Who | Expression and pose | Props and motif |
| --- | --- | --- | --- | --- | --- |
| `first-run-welcome` | 1 | The first screen of a new account, and the welcome of each app | Lorenzo | Warm Smile; an open hand offered toward the viewer; half-body | An open atlas in the other hand; three small world discs behind them (a castle, an orbital station, an apartment block) |
| `empty-entries` | 1 | A list of entries with nothing in it yet. Words beside it: "No entries yet. Add a person, place, event, object, or whatever else exists here." | Lorenzo | Curious / Intrigued; a head tilt; half-body | A blank index card held up; a few more blank cards floating, each a different shape |
| `empty-notes` | 1 | A place with no notes yet | Lorenzo and Catileo | Lorenzo: Focused / Analytical, writing. Catileo: the paw-on-page pose, Mildly Judgmental | A single page; a pen. Catileo is on the page |
| `empty-manuscript` | 1 | Writing, with nothing written | Catileo | Book sleep or curled sleep; Slow-Blink Contentment | A blank page under the cat; a closed ink bottle |
| `empty-map` | 1 | Maps, with no map yet | Lorenzo and Catileo | Lorenzo: Curious, unrolling a blank map. Catileo: map occupation, sitting at the exact centre | A blank sheet with a faint grid; a compass |
| `empty-inventory` | 1 | An inventory or board with nothing carried | Catileo | Curious; sitting in an empty satchel, looking out | An open leather satchel; nothing else |
| `empty-sessions` | 1 | Sessions, with none planned or assigned. Words beside it: "No Session yet. You will see a Session here once a GM assigns you to it." | Lorenzo and Catileo | Lorenzo: Warm Smile, holding a planner. Catileo: asleep on the planner (loaf) | A blank calendar page |
| `empty-beings` | 2 | Beings, with no characters yet | Lorenzo | Curious; half-body | An empty character sheet with a silhouette outline; a pencil |
| `empty-calendar` | 3 | Calendars, with none authored | Lorenzo | Focused / Analytical; half-body | A blank month grid; a small hourglass |
| `caught-up` | 1 | Notifications with nothing new. Words beside it: "You're all caught up." | Catileo | Curled sleep; Slow-Blink Contentment | A folded blanket; nothing else |

### Errors and unavailable

| ID | Priority | Where | Who | Expression and pose | Props and motif |
| --- | --- | --- | --- | --- | --- |
| `page-not-found` | 1 | A page that does not exist. Words beside it: "Catileo appears to have misplaced this page." (identity §14.2) | Catileo | Mildly Judgmental, looking away from the camera; sitting beside a page-shaped empty spot on the floor | A paw print on the empty spot; one loose corner of paper |
| `no-access` | 1 | A page the person may not open. Words: "This page isn't available." | Catileo | Neutral / Regal; the doorway observer, sitting before a closed door | A closed door with a small cat flap |
| `offline-page` | 2 | A whole app that cannot start offline | Lorenzo and Catileo | Lorenzo: calm, reading by a lantern. Catileo: asleep nearby | A lantern; an unplugged cable looped on the floor |
| `error-page` | 1 | A failure that replaces the whole page | Catileo | Startled; the sudden vertical alert, next to a toppled stack | A stack of papers mid-fall; the cat is not at fault and does not look it |
| `maintenance` | 3 | Planned downtime | Lorenzo | Warm Smile with an apologetic tilt; half-body | A small toolbox; a closed notebook |

### Moments

| ID | Priority | Where | Who | Expression and pose | Props and motif |
| --- | --- | --- | --- | --- | --- |
| `first-entry` | 2 | Once, after the first entry is created | Lorenzo | Bright Delight; half-body | A single index card, filled in, held up |
| `published` | 3 | Once, after a repository is first published | Lorenzo | Warm Smile; handing a bound volume to the viewer | A bound book with a gold spark on the cover |
| `no-results` | 3 | A full page of search results with nothing found | Lorenzo | Skeptical, one brow high; half-body | A magnifying glass held up to an empty page |

### Small heads (level L5)

For help text and documentation only. Never in app chrome, never repeated in every panel (identity §9.3).

| ID | Priority | Who | Set |
| --- | --- | --- | --- |
| `head-lorenzo` | 3 | Lorenzo | Neutral, Warm Smile, Curious, Concerned / Empathetic; head only, flat fills, minimal lines |
| `head-catileo` | 3 | Catileo | Neutral / Regal, Slow-Blink Contentment, Mildly Judgmental, Sleepy; head only, flat fills |

## Where no mascot is used

A functional problem inside a working page uses an icon and words, not a mascot: a failed load of one list, a conflict, a field error, a permission note on a control, a toast, the sync state. A branded wait uses the spark, not a character (identity §17.9). The mascots appear where a whole page has nothing to show or cannot be shown, so they stay rare.
