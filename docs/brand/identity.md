# Lorenzo — Brand Identity

version: 1.0
status: living specification
updated: 2026-09-23
scope: master brand, product family, digital applications, developer tools, community surfaces

---

## 0. Purpose of this document

This document defines the Lorenzo identity as a practical system rather than a collection of isolated assets. It is the reference for product design, websites, apps, Discord bots, CLI tools, documentation, developer interfaces, social surfaces, community material, print, merchandise, and future Lorenzo-branded products.

The goal is consistency without stiffness. Lorenzo should be recognizable from a favicon, a terminal line, a login screen, a book-sized poster, or a mascot illustration without forcing every touchpoint to look identical.

When rules conflict, prefer the choice that preserves these three things in order:

1. Recognition: does this still unmistakably feel like Lorenzo?
2. Clarity: does the interface or message remain easy to understand and use?
3. Character: does the brand retain its scholarly, curious, slightly cosmic personality?

---

## 1. Brand core

### 1.1 What Lorenzo is

Lorenzo is world, campaign, and character bookkeeping for game masters, players, authors, and worldbuilders.

It is designed for the things people actually juggle when maintaining fictional realities: where something is physically and conceptually; which world, plane, timeline, or multiverse it belongs to; who knows what about whom; which repositories or settings a game draws from; and the text, statistics, secrets, permissions, and relationships attached to every person, place, item, event, and idea.

Lorenzo must feel equally at home beside a one-shot fantasy adventure, a decades-long science-fiction campaign, a historical mystery, a Warhammer setting, a novel, or an absurdly complicated shared multiverse.

### 1.2 Brand idea

**Keep track of worlds.**

The core visual and verbal tension is:

**old-world scholarship × modern information system.**

Lorenzo should suggest archives, atlases, notes, relationships, navigation, knowledge, maps, and discovery without becoming medieval, heraldic, or genre-specific.

### 1.3 Personality

Lorenzo is:

- scholarly, but not academic for its own sake
- curious, but not whimsical to the point of distraction
- meticulous, but not bureaucratic
- warm, but not cute-first
- elegant, but not luxurious or precious
- modern, but not sterile
- slightly eccentric, but never chaotic
- confident, but not grandiose

A useful shorthand is:

> **Scholar, not wizard. Archivist, not administrator. Worlds, not fantasy worlds.**

### 1.4 Brand principles

#### Worlds, not genre

Lorenzo may contain castles, starships, apartment blocks, alien moons, Victorian detectives, family trees, corporations, gods, train stations, parallel dimensions, and mundane coffee shops in the same visual universe.

Avoid visual language that makes fantasy feel like the default mode.

#### Historic voice, modern system

The custom wordmark and editorial serif give Lorenzo its literary and historical voice. The product UI, data visualization, navigation, forms, tables, graphs, and developer surfaces should remain contemporary and highly legible.

#### Gold is punctuation

Medici Gold is an accent, not a surface treatment. It marks identity, significance, and special moments. It should not turn Lorenzo into a heraldic or faux-luxury brand.

#### Personality lives in illustration

The mascot can be expressive, human, warm, and detailed. The core product identity remains disciplined and reduced.

#### One memorable gesture

The four-point spark is the recurring gesture of the system. Do not compete with it by introducing additional crests, monograms, compass roses, magical sigils, or unrelated star symbols.

---

## 2. Identity system at a glance

Lorenzo has several identity layers. They are complementary, not interchangeable.

| Layer                      | Meaning                     | Primary role                                              |
| -------------------------- | --------------------------- | --------------------------------------------------------- |
| **Lorenzo**                | verbal identity             | product and company name                                  |
| **Custom wordmark**        | typographic identity        | formal brand signature                                    |
| **Four-point spark**       | core visual identity        | brand mark, iconography, shorthand                        |
| **Shaded spark**           | expressive mark             | hero moments, lockups, loader, richer digital use         |
| **`✧`**                    | typographic shorthand       | plain text, CLI, release notes, lightweight community use |
| **Lorenzo, the character** | mascot/personality          | onboarding, illustration, community, storytelling         |
| **Catileo**                | supporting mascot character | warmth, humor, secondary illustration moments             |
| **Mascot emblem**          | secondary badge             | stickers, community, merch, editorial brand moments       |

The most important distinction is:

> **The spark is Lorenzo the brand. Lorenzo the character is Lorenzo the mascot.**

The mascot may change pose, clothing, context, medium, expression, and scene. The spark does not need to change.

---

## 3. Naming and verbal notation

### 3.1 Master name

Always write the brand name as **Lorenzo**.

Do not stylize it as LORENZO, lorenzo, LorenZo, or with decorative punctuation in ordinary copy.

### 3.2 Text shorthand: `✧`

`✧` is the official ultra-shorthand expression of the spark in text-only environments.

Approved examples:

- `✧ Lorenzo`
- `Built with ✧ Lorenzo`
- `✧ Canonical`
- `✧ Lorenzo CLI`
- `Welcome to Lorenzo ✧`

Use it where actual SVG artwork would be awkward or impossible: terminals, source comments, plain-text changelogs, bot messages, release notes, IRC-like interfaces, low-fidelity documentation, or conversational community spaces.

Do not use `✧` as a substitute for the actual brand mark in polished visual design when the SVG is available.

If the glyph is not supported by an environment, use **Lorenzo** without a replacement symbol. Do not substitute `*`, `+`, `★`, or random Unicode stars.

### 3.3 Product-family naming

Lorenzo is the master brand. Future tools should remain visibly part of the same family.

Preferred pattern:

- Lorenzo CLI
- Lorenzo Bot
- Lorenzo Sync
- Lorenzo API
- Lorenzo Mobile
- Lorenzo for Discord

Use descriptive product names rather than inventing a separate brand for every utility.

Sub-products do not receive their own logo marks. They inherit the Lorenzo spark and wordmark. A product descriptor may be set beside the main identity in the UI typeface.

Example:

`✧ Lorenzo` `CLI`

The descriptor is secondary and should never be redrawn into the custom wordmark.

---

## 4. Logo system

### 4.1 Core assets

The current official asset set is:

| Asset                                      | Role                                   | Recommended use                                     |
| ------------------------------------------ | -------------------------------------- | --------------------------------------------------- |
| `brand_mark.svg`                           | colored unshaded brand mark            | general standalone brand mark                       |
| `brand_mark_shaded.svg`                    | colored shaded brand mark              | expressive digital mark, hero moments, loaders      |
| `brand_mark_monochrome.svg`                | monochrome unshaded mark               | maximum flexibility, tiny UI, print, engraving      |
| `brand_mark_shaded_monochrome.svg`         | monochrome shaded mark                 | richer single-color digital use                     |
| `wordmark_full.svg`                        | full signature composition             | formal centered brand presentation                  |
| `wordmark_light_bg.svg`                    | wordmark for light backgrounds         | marketing, docs, light UI surfaces                  |
| `wordmark_dark_bg.svg`                     | reversed wordmark for dark backgrounds | dark UI and dark marketing surfaces                 |
| `wordmark_monochrome.svg`                  | single-color wordmark                  | print, one-color production, flexible use           |
| `lorenzo_horizontal_lockup_light_bg.svg`   | gold shaded mark + Ink wordmark        | default horizontal logo on light surfaces           |
| `lorenzo_horizontal_lockup_dark_bg.svg`    | gold shaded mark + Paper wordmark      | default horizontal logo on dark surfaces            |
| `lorenzo_horizontal_lockup_monochrome.svg` | monochrome horizontal lockup           | single-color or production-constrained use          |
| `mascot_emblem.png`                        | illustrated mascot badge               | community, stickers, merch, editorial brand moments |
| `mascot_emblem_web.png`                    | web-optimized mascot emblem derivative | README hero art and other size-constrained embeds   |
| `mascot.png`                               | Lorenzo mascot illustration            | onboarding, product illustration, social, editorial |
| `social_banner.png`                        | full illustrated social banner master  | source art for social/OG preview images             |
| `social_banner_github.png`                 | GitHub social preview derivative       | Settings → Social preview (1280×640, under 1MB)     |

Treat SVG files as the preferred production masters for marks and lockups. Keep the mascot artwork as high-resolution raster artwork unless a deliberate simplified vector redraw is commissioned. Do not auto-trace the mascot illustration into a large, noisy SVG.

### 4.2 Logo hierarchy

#### Primary product lockup

Use the horizontal lockup for most product and interface contexts:

`✧ Lorenzo`

This is the preferred header, navigation, documentation, product-shell, developer-portal, and partner-placement expression.

#### Signature wordmark

Use the centered wordmark with the supporting spark for moments where vertical room exists and the brand is the focal point: landing-page heroes, title screens, press pages, posters, cover pages, presentation openings, and formal brand moments.

#### Brand mark alone

Use the spark alone when space is constrained or recognition is already established: favicon, app icon basis, UI brand stamp, launcher icon, social avatar, watermark.

This is about using the spark *as the logo itself* at reduced size — it is not a license to reach for it as interface iconography. See §17 for the boundary between brand identity and conventional UI icons (loading indicators, selection states, and per-user avatar placeholders use ordinary interface treatments, not the spark).

#### Mascot emblem

The mascot emblem is a secondary brand signature, not the primary logo. It is intentionally richer, more illustrative, and more expressive.

Use it for stickers, community graphics, merch, event material, README hero art, editorial moments, social posts, or an “About Lorenzo” context.

Do not use it as the favicon, app icon, routine navigation logo, or tiny UI identity.

### 4.3 Brand mark construction

The official spark is a bespoke four-point form with a self-similar negative-space aperture at its center.

It is not a generic Unicode star, compass rose, sparkle icon, or font glyph.

The mark should always preserve:

- the vertically biased four-point silhouette
- smooth concave transitions
- the central negative-space spark
- the exact arm proportions
- the exact orientation

Do not redraw the mark from memory.

### 4.4 Shaded mark construction

The shaded mark preserves the exact base geometry and adds only two flat overlay systems.

Canonical shading behavior:

- north sector: no shade
- east sector: black at 7% opacity
- west sector: black at 7% opacity
- south sector: black at 14% opacity

Canonical highlight behavior:

- west-facing half of north arm: white at 12%
- north-facing half of east arm: white at 12%
- north-facing half of west arm: white at 12%
- west-facing half of south arm: white at 10%

The center aperture remains true negative space through all overlays.

The effect should read as a hint of flat faux-dimensionality, not a gradient, bevel, chrome effect, emboss, glow, or 3D render.

Do not rotate the shade or highlight layers independently from the base mark.

### 4.5 Choosing shaded vs. unshaded

Use **unshaded** when:

- the mark is very small
- reproduction is constrained
- the context is utilitarian or technical
- print, engraving, embroidery, monochrome stamping, or embossing demands simplicity
- the mark appears repeatedly in dense UI

Use **shaded** when:

- the mark is part of a hero identity moment
- the horizontal lockup is used
- the mark is a loader or motion element
- a little more visual richness helps without adding complexity
- the mark is shown at approximately 24 px or larger

The two versions are variants of the same identity, not separate marks.

### 4.6 Clearspace

Use the height of the **inner negative-space spark** as the clearspace unit `x`.

Minimum clearspace:

- standalone spark: `1x` on all sides
- horizontal lockup: `1x` around the complete lockup
- centered signature wordmark: `1x` around the complete composition
- mascot emblem: at least `1x` from other logos or hard edges

More space is encouraged in editorial and marketing compositions.

### 4.7 Minimum sizes

Recommended digital minimums:

- unshaded spark: 16 px
- shaded spark: 24 px
- custom wordmark: 140 px wide
- horizontal lockup: 220 px wide
- mascot emblem: 160 px wide for meaningful detail

Below these thresholds, move to a simpler identity level rather than forcing detail to survive.

For very small spaces, prefer the spark alone.

### 4.8 Background behavior

#### Light surfaces

Preferred:

- Ink wordmark + Medici Gold mark
- Lorenzo Ink monochrome mark
- colored Gold brand mark

#### Dark surfaces

Preferred:

- Paper wordmark + Medici Gold mark
- Paper or light monochrome mark
- colored Gold brand mark where contrast is sufficient

#### Photography and complex imagery

Do not place the logo directly over noisy areas. Use a calm field, crop, scrim, or dedicated brand surface.

Avoid outlines and drop shadows as a rescue technique.

### 4.9 Logo misuse

Do not:

- stretch, skew, condense, or rotate the logo
- change the relative position of mark and wordmark inside official lockups
- substitute a font for the custom wordmark
- redraw the spark as a generic star
- put the logo inside a shield, crest, heraldic frame, ornate scroll, or fantasy badge
- use metallic gradients or shiny “gold” effects
- add glows, bevels, shadows, embossing, or lens flares
- recolor individual letters
- make the center aperture opaque
- place the mascot emblem where a simple logo is required
- create different logo marks for each Lorenzo sub-product

---

## 5. Typography

### 5.1 Wordmark versus typeface

The Lorenzo wordmark is artwork. It is not a typesetting instruction.

Never attempt to reproduce the wordmark by typing “Lorenzo” in a serif font.

The product typography system should complement the wordmark, not imitate it.

### 5.2 Recommended type system

#### Interface and body — Geist

Use **Geist** for:

- navigation
- forms
- buttons
- tables
- metadata
- body text
- settings
- labels
- system messages
- web and app UI

Its role is clarity, density control, and modernity.

Fallback stack:

`Geist, Inter, ui-sans-serif, system-ui, sans-serif`

#### Editorial and display — Newsreader

Use **Newsreader** selectively for:

- large campaign or world titles
- landing-page headlines
- editorial section titles
- narrative introductions
- empty-state titles
- selected entity names where a literary tone is useful

Do not use it for dense forms, long tables, small metadata, or developer tooling.

Fallback stack:

`"Newsreader", Georgia, "Times New Roman", serif`

#### Code and developer surfaces — Geist Mono

Use **Geist Mono** for:

- CLI examples
- IDs
- API payloads
- code snippets
- paths
- schema fields
- timestamps where monospacing improves scanning

Fallback stack:

`"Geist Mono", "SFMono-Regular", Consolas, monospace`

### 5.3 Typographic hierarchy

A practical starting scale:

| Role         | Typeface                  | Typical size | Weight / style |
| ------------ | ------------------------- | -----------: | -------------- |
| Hero display | Newsreader                |     48–72 px | Regular        |
| H1           | Newsreader or Geist       |     36–48 px | Regular / 600  |
| H2           | Geist                     |     28–36 px | 600            |
| H3           | Geist                     |     20–24 px | 600            |
| Entity title | Newsreader                |     24–32 px | Regular        |
| Body         | Geist                     |     15–17 px | 400            |
| UI           | Geist                     |     13–15 px | 400–500        |
| Metadata     | Geist                     |     12–13 px | 400–500        |
| Code         | Geist Mono                |     12–14 px | 400            |

Do not overuse the serif. Its scarcity is what gives it personality.

### 5.4 Typographic character

Prefer:

- sentence case
- calm line lengths
- comfortable leading
- restrained weight contrast
- tabular numbers where data scanning benefits
- clear hierarchy through size and space before color

Avoid:

- fake small caps
- faux-medieval display faces
- blackletter
- ornamental fantasy fonts
- excessive all caps
- tracking that makes the brand feel luxury-fashion oriented

---

## 6. Color system

### 6.1 Core palette

| Name             | Hex       | Role                                                                              |
| ---------------- | --------- | --------------------------------------------------------------------------------- |
| **Lorenzo Ink**  | `#08131F` | primary text, logo, dark UI, deep surfaces                                        |
| **Archive Blue** | `#1769C2` | primary interaction color, links, active states                                   |
| **Astral Blue**  | `#3B91E8` | highlights, illustrative accents, selected details                                |
| **Medici Gold**  | `#B88A3B` | brand mark, special accents, meaningful punctuation                               |
| **Parchment**    | `#F4EFE5` | warm editorial surfaces, illustration fields                                      |
| **Paper**        | `#FBFAF7` | primary light background                                                          |
| **Burgundy**     | `#7B2638` | rare secondary accent — destructive/dangerous states, genuinely dramatic emphasis |

### 6.2 Palette logic

**Ink + Paper** provide the foundation.

**Archive Blue** provides interaction.

**Medici Gold** provides identity.

**Astral Blue** provides visual energy and connects the system to the mascot’s blue details.

**Parchment** adds warmth without resorting to literal parchment textures.

**Burgundy** is a controlled secondary accent, not a second primary brand color. It signals destructive or dangerous actions and genuinely dramatic narrative beats — never secrecy or restricted visibility, which is deliberately color-neutral instead (§6.6).

### 6.3 Usage proportions

A typical interface should feel approximately:

- 70–85% neutral Paper / Ink / neutralized surfaces
- 10–20% Archive Blue and related interactive states
- 2–5% Medici Gold
- 0–5% Astral Blue or Burgundy depending on context

This is a visual tendency, not a mathematical requirement.

Gold should feel like punctuation. If the screen feels “gold-themed,” too much gold is being used.

### 6.4 Neutral system

Do not introduce a large unrelated gray palette unless needed for accessibility or platform conventions.

Prefer neutrals derived from Ink and Paper through opacity:

Light theme examples:

- primary text: Ink 100%
- secondary text: Ink 70%
- tertiary text: Ink 50–55%
- border: Ink 14–18%
- soft fill: Ink 5–8%

Dark theme examples:

- primary text: Paper 100%
- secondary text: Paper 75%
- tertiary text: Paper 55%
- border: Paper 14–18%
- soft fill: Paper 6–9%

These ratios are now codified as concrete custom properties — `--text-secondary`, `--text-tertiary`, `--border-subtle`, `--fill-soft`, and the rest of the semantic layer — in §6.6, so every app reads the same values instead of re-deriving them.

### 6.5 Accessibility notes

Approximate contrast behavior against Paper / Ink:

- Ink on Paper: excellent for all text
- Archive Blue on Paper: suitable for normal interactive text
- Astral Blue on Paper: best for large text, icons, or non-text accents rather than small body text
- Medici Gold on Paper: do not use for small text; use it for marks, icons, large decorative type, or non-text emphasis
- Medici Gold on Ink: strong enough for many meaningful dark-theme accents
- Burgundy on Paper: strong text contrast
- Burgundy on Ink: avoid for small text

Never communicate state through color alone. Pair color with labels, icons, shape, position, or text.

### 6.6 Semantic color roles and tokens

§6.1–6.5 define the *palette* — seven colors and how they should feel. With `apps/api` now standing behind multiple real apps (`apps/inventory-web`, `apps/account-hub`, more to come), that's no longer enough on its own: every app needs to reach for the same name for "the border on a normal card" or "the background of a destructive button" instead of each one improvising its own reading of Ink-at-some-opacity. This section is that shared vocabulary — a semantic layer that sits on top of the palette and is what product code actually consumes.

#### Primitives, utility colors, and semantic roles

Three tiers, each with one job:

1. **Brand primitives** (§6.1) — Ink, Archive Blue, Astral Blue, Medici Gold, Parchment, Paper, Burgundy. Identity-level. Product code should not reference these directly.
2. **Utility colors** — two additions, for meanings the seven primitives have no honest answer to: a muted archival green for success, a darker ochre for warning. Neither reads as a plausible tint of Ink, either Blue, Gold, or Burgundy, so rather than force one of them into a job it doesn't fit, these get their own small, brand-adjacent tier. They are not brand colors and don't appear in §6.1.
3. **Semantic roles** — the tokens below (`--surface-default`, `--text-primary`, `--action-hover`, `--danger`, and so on). Named for the job, not the color. This is the tier every app actually styles against.

Wherever a semantic role's exact color can be reached by transforming a primitive or utility color, it's defined that way — `color-mix()` of two named colors, never a fresh literal — so the relationship stays legible in the source instead of two independently-typed hex codes silently drifting apart. A handful of dark-theme accents (marked below) are hand-tuned, perceptually lightened variants that a flat `color-mix()` genuinely can't reproduce; those stay literal, on purpose.

The governing idea:

| Meaning                 | Color family                   |
| ----------------------- | ------------------------------ |
| Normal information      | Ink / Paper                    |
| Interaction             | Archive Blue / Astral Blue     |
| Canonical / significant | Medici Gold                    |
| Success                 | muted archival green (utility) |
| Warning                 | darker ochre (utility)         |
| Danger / destructive    | Burgundy                       |

Astral Blue additionally stands alone as a supporting interaction/visualization color — `--focus-ring`, `--graph-highlight`, `--illustration-blue` — independent of whichever blue `--action` currently is in the active theme.

Medici Gold keeps exactly one meaning: canonical, significant, Lorenzo identity itself (a canonical repository, a source world, the spark, a rare editorial mark of provenance). It is never warning, premium, selected, interactive, or "the important button" — this was already true per §1.4 and §6.3; this section just makes it load-bearing rather than a style note.

#### Visibility is neutral, not colored

Domain visibility — private, GM-only, visible to a selected group, or public (see [docs/domain/entities-knowledge-and-visibility.md](../domain/entities-knowledge-and-visibility.md)) — is a fact about who can see something, not a warning, an error, or a dramatic state. It gets no color of its own, and specifically never Burgundy: reusing a "destructive/dramatic" color for "restricted" conflates two unrelated concepts and was never a deliberate design decision to begin with.

Every non-public tier shares one neutral treatment — `--visibility-restricted-surface/-text/-border` — regardless of which tier it is; only an icon and a label say which one:

| Icon (placeholder — real SVG icons come later) | Tier                     |
| ---------------------------------------------- | ------------------------ |
| 🔒                                             | Private                  |
| ◉                                              | GM only                  |
| 👥                                             | Selected characters      |
| *(none)*                                       | Public — no badge at all |

Public is the unmarked default and needs no badge; only a restriction needs to say so.

#### Buttons are their own layer

Buttons and inline links both key off `--action`, but a button is a distinct component with its own background/foreground/hover — not the same rule as coloring a piece of text. Keeping `--button-*` as its own small namespace (defined in terms of the roles above, never a fresh literal) means it pushes zero net-new colors into the system and inherits dark-theme behavior automatically.

#### Light theme

| Token                             | Derivation                           | Value     | Intended use                           |
| --------------------------------- | ------------------------------------ | --------- | -------------------------------------- |
| `--surface-canvas`                | Paper                                | `#FBFAF7` | page/app background                    |
| `--surface-default`               | Paper                                | `#FBFAF7` | cards, panels, normal surfaces         |
| `--surface-muted`                 | Paper 96% / Ink 4%                   | `#F1F1EE` | table headers, subdued sections        |
| `--surface-warm`                  | Parchment                            | `#F4EFE5` | editorial/narrative moments            |
| `--surface-selected`              | Paper 88% / Archive Blue 12%         | `#E0E9F1` | selected rows/cards/nodes              |
| `--fill-soft`                     | Ink 6%, translucent over its surface | —         | transient hover/badge tint (unchanged) |
| `--text-primary`                  | Ink                                  | `#08131F` | normal text                            |
| `--text-secondary`                | Ink 70% / Paper 30%                  | `#515860` | supporting text                        |
| `--text-tertiary`                 | Ink 55% / Paper 45%                  | `#757B80` | metadata, timestamps                   |
| `--text-inverse`                  | Paper                                | `#FBFAF7` | text on dark/blue surfaces             |
| `--border-subtle`                 | Ink 16% / Paper 84%                  | `#D4D5D4` | normal component borders               |
| `--border-strong`                 | Ink 24% / Paper 76%                  | `#C1C3C3` | emphasized separators                  |
| `--action`                        | Archive Blue                         | `#1769C2` | links, interactive text                |
| `--action-hover`                  | Archive Blue 85% / Ink 15%           | `#155CAA` | hover/pressed interactive text         |
| `--action-surface`                | Paper 92% / Archive Blue 8%          | `#E9EEF3` | subtle blue control background         |
| `--action-selected`               | = `--surface-selected`               | `#E0E9F1` | selected state                         |
| `--focus-ring`                    | Astral Blue                          | `#3B91E8` | keyboard focus                         |
| `--graph-highlight`               | Astral Blue                          | `#3B91E8` | graph/relationship-diagram accents     |
| `--illustration-blue`             | Astral Blue                          | `#3B91E8` | non-text illustrative accents          |
| `--canonical`                     | Medici Gold                          | `#B88A3B` | canonical/significant identity         |
| `--canonical-surface`             | Paper 92% / Gold 8%                  | `#F6F1E8` | subtle canonical emphasis              |
| `--success`                       | utility-success                      | `#2F6F56` | positive status                        |
| `--success-surface`               | Paper 92% / utility-success 8%       | `#EBEFEA` | positive notice background             |
| `--warning`                       | utility-warning                      | `#7A5A1F` | caution                                |
| `--warning-surface`               | Paper 92% / utility-warning 8%       | `#F1EDE6` | caution background                     |
| `--danger`                        | Burgundy                             | `#7B2638` | destructive/error state                |
| `--danger-surface`                | Paper 92% / Burgundy 8%              | `#F1E9E8` | destructive/error background           |
| `--visibility-restricted-surface` | = `--surface-muted`                  | `#F1F1EE` | any non-public visibility badge        |
| `--visibility-restricted-text`    | = `--text-primary`                   | `#08131F` | any non-public visibility badge        |
| `--visibility-restricted-border`  | = `--border-strong`                  | `#C1C3C3` | any non-public visibility badge        |
| `--button-primary-bg`             | = `--action`                         | `#1769C2` | primary button background              |
| `--button-primary-fg`             | = `--text-inverse`                   | `#FBFAF7` | primary button text                    |
| `--button-primary-hover`          | = `--action-hover`                   | `#155CAA` | primary button hover                   |
| `--button-secondary-bg`           | transparent                          | —         | secondary button background            |
| `--button-secondary-fg`           | = `--text-primary`                   | `#08131F` | secondary button text                  |
| `--button-secondary-border`       | = `--border-strong`                  | `#C1C3C3` | secondary button border                |
| `--button-danger-bg`              | = `--danger`                         | `#7B2638` | destructive button background          |
| `--button-danger-fg`              | = `--text-inverse`                   | `#FBFAF7` | destructive button text                |

#### Dark theme

Every token not listed here is unchanged from the light theme.

| Token                 | Derivation                             | Value     |
| --------------------- | -------------------------------------- | --------- |
| `--surface-canvas`    | Ink                                    | `#08131F` |
| `--surface-default`   | Ink 96% / Paper 4%                     | `#121C28` |
| `--surface-muted`     | Ink 92% / Paper 8%                     | `#1B2530` |
| `--surface-warm`      | Ink 84% / Gold 16%                     | `#242623` |
| `--surface-selected`  | hand-tuned — not a plain mix           | `#1B3044` |
| `--fill-soft`         | Paper 7%, translucent over its surface | —         |
| `--text-primary`      | Paper                                  | `#FBFAF7` |
| `--text-secondary`    | Ink 25% / Paper 75%                    | `#BEC0C1` |
| `--text-tertiary`     | Ink 45% / Paper 55%                    | `#8E9296` |
| `--text-inverse`      | Ink                                    | `#08131F` |
| `--border-subtle`     | Ink 84% / Paper 16%                    | `#2F3842` |
| `--border-strong`     | Ink 76% / Paper 24%                    | `#424A53` |
| `--action`            | Astral Blue (replaces Archive Blue)    | `#3B91E8` |
| `--action-hover`      | Astral Blue 85% / Paper 15%            | `#58A1EA` |
| `--action-surface`    | hand-tuned — not a plain mix           | `#172637` |
| `--action-selected`   | hand-tuned — not a plain mix           | `#1B3044` |
| `--focus-ring`        | = `--action-hover`                     | `#58A1EA` |
| `--graph-highlight`   | Astral Blue (unchanged)                | `#3B91E8` |
| `--illustration-blue` | Astral Blue (unchanged)                | `#3B91E8` |
| `--canonical`         | Gold (unchanged)                       | `#B88A3B` |
| `--canonical-surface` | Ink 84% / Gold 16%                     | `#242623` |
| `--success`           | hand-tuned — not a plain mix           | `#6FC29A` |
| `--success-surface`   | Ink 75% / utility-success 25%          | `#14282E` |
| `--warning`           | hand-tuned — not a plain mix           | `#D7AA52` |
| `--warning-surface`   | Ink 78% / utility-warning 22%          | `#212525` |
| `--danger`            | hand-tuned — not a plain mix           | `#E47A8D` |
| `--danger-surface`    | hand-tuned — not a plain mix           | `#221F2C` |

`--action` swapping from Archive Blue to Astral Blue in dark mode isn't new — it's the existing convention every shipped app already follows. What's new here is that `--focus-ring` now tracks that swap deliberately: in light mode it's Astral Blue standing apart from Archive-Blue `--action`; once `--action` itself becomes Astral Blue in dark mode, the focus ring borrows `--action-hover`'s lighter tint instead, so a focused element still reads as distinct from a plain link in both themes — not two unrelated hardcoded values.

The `--visibility-restricted-*` and `--button-*` tokens are all aliases (`--visibility-restricted-surface: var(--surface-muted)`, etc.), so they need no dark-theme entries of their own — they inherit correctly for free.

#### Starter

```css
:root {
  color-scheme: light;

  /* Brand primitives (§6.1) — identity only, never referenced directly by product UI */
  --brand-ink: #08131f;
  --brand-archive-blue: #1769c2;
  --brand-astral-blue: #3b91e8;
  --brand-gold: #b88a3b;
  --brand-parchment: #f4efe5;
  --brand-paper: #fbfaf7;
  --brand-burgundy: #7b2638;

  /* Utility colors — genuinely new hues, not tints of a brand primitive */
  --utility-success: #2f6f56;
  --utility-warning: #7a5a1f;

  /* Surfaces */
  --surface-canvas: var(--brand-paper);
  --surface-default: var(--brand-paper);
  --surface-muted: color-mix(in srgb, var(--brand-paper) 96%, var(--brand-ink) 4%);
  --surface-warm: var(--brand-parchment);
  --surface-selected: color-mix(in srgb, var(--brand-paper) 88%, var(--brand-archive-blue) 12%);
  --fill-soft: color-mix(in srgb, var(--brand-ink) 6%, transparent);

  /* Text */
  --text-primary: var(--brand-ink);
  --text-secondary: color-mix(in srgb, var(--brand-ink) 70%, var(--brand-paper));
  --text-tertiary: color-mix(in srgb, var(--brand-ink) 55%, var(--brand-paper));
  --text-inverse: var(--brand-paper);

  /* Borders */
  --border-subtle: color-mix(in srgb, var(--brand-ink) 16%, var(--brand-paper));
  --border-strong: color-mix(in srgb, var(--brand-ink) 24%, var(--brand-paper));

  /* Interaction */
  --action: var(--brand-archive-blue);
  --action-hover: color-mix(in srgb, var(--brand-archive-blue) 85%, var(--brand-ink) 15%);
  --action-surface: color-mix(in srgb, var(--brand-paper) 92%, var(--brand-archive-blue) 8%);
  --action-selected: var(--surface-selected);
  --focus-ring: var(--brand-astral-blue);
  --graph-highlight: var(--brand-astral-blue);
  --illustration-blue: var(--brand-astral-blue);

  /* Canonical / significant — Gold's one job (§6.6) */
  --canonical: var(--brand-gold);
  --canonical-surface: color-mix(in srgb, var(--brand-paper) 92%, var(--brand-gold) 8%);

  /* Status */
  --success: var(--utility-success);
  --success-surface: color-mix(in srgb, var(--brand-paper) 92%, var(--utility-success) 8%);
  --warning: var(--utility-warning);
  --warning-surface: color-mix(in srgb, var(--brand-paper) 92%, var(--utility-warning) 8%);
  --danger: var(--brand-burgundy);
  --danger-surface: color-mix(in srgb, var(--brand-paper) 92%, var(--brand-burgundy) 8%);

  /* Buttons are their own layer, defined only in terms of roles above */
  --button-primary-bg: var(--action);
  --button-primary-fg: var(--text-inverse);
  --button-primary-hover: var(--action-hover);
  --button-secondary-bg: transparent;
  --button-secondary-fg: var(--text-primary);
  --button-secondary-border: var(--border-strong);
  --button-danger-bg: var(--danger);
  --button-danger-fg: var(--text-inverse);

  /* Visibility is deliberately color-neutral — every non-public tier
     (private, GM-only, a selected group) shares this one treatment;
     only the icon/label changes. Public needs no badge at all. */
  --visibility-restricted-surface: var(--surface-muted);
  --visibility-restricted-text: var(--text-primary);
  --visibility-restricted-border: var(--border-strong);
}

[data-theme="dark"] {
  color-scheme: dark;

  --surface-canvas: var(--brand-ink);
  --surface-default: color-mix(in srgb, var(--brand-ink) 96%, var(--brand-paper) 4%);
  --surface-muted: color-mix(in srgb, var(--brand-ink) 92%, var(--brand-paper) 8%);
  --surface-warm: color-mix(in srgb, var(--brand-ink) 84%, var(--brand-gold) 16%);
  /* hand-tuned — a flat mix of any two named colors here undershoots the
     intended blue cast; don't try to re-derive it mechanically */
  --surface-selected: #1b3044;
  --fill-soft: color-mix(in srgb, var(--brand-paper) 7%, transparent);

  --text-primary: var(--brand-paper);
  --text-secondary: color-mix(in srgb, var(--brand-ink) 25%, var(--brand-paper));
  --text-tertiary: color-mix(in srgb, var(--brand-ink) 45%, var(--brand-paper));
  --text-inverse: var(--brand-ink);

  --border-subtle: color-mix(in srgb, var(--brand-ink) 84%, var(--brand-paper) 16%);
  --border-strong: color-mix(in srgb, var(--brand-ink) 76%, var(--brand-paper) 24%);

  /* Astral replaces Archive for readable dark-mode interaction (unchanged
     from the existing --action light-dark() pairing) */
  --action: var(--brand-astral-blue);
  --action-hover: color-mix(in srgb, var(--brand-astral-blue) 85%, var(--brand-paper) 15%);
  /* hand-tuned, same reasoning as --surface-selected above */
  --action-surface: #172637;
  --action-selected: #1b3044;

  /* Astral Blue now equals --action, so the focus ring borrows
     --action-hover's lighter tint instead, to stay visually distinct from
     a plain link the way it already is in light mode. */
  --focus-ring: var(--action-hover);
  --graph-highlight: var(--brand-astral-blue);
  --illustration-blue: var(--brand-astral-blue);

  --canonical: var(--brand-gold);
  --canonical-surface: color-mix(in srgb, var(--brand-ink) 84%, var(--brand-gold) 16%);

  /* These three are hand-tuned (hue held, lightness/saturation raised) —
     a plain color-mix() toward Ink or Paper can't reproduce a perceptual
     lighten, so don't try to derive them mechanically if they ever change. */
  --success: #6fc29a;
  --success-surface: color-mix(in srgb, var(--brand-ink) 75%, var(--utility-success) 25%);
  --warning: #d7aa52;
  --warning-surface: color-mix(in srgb, var(--brand-ink) 78%, var(--utility-warning) 22%);
  --danger: #e47a8d;
  --danger-surface: #221f2c;

  --visibility-restricted-surface: var(--surface-muted);
  --visibility-restricted-text: var(--text-primary);
  --visibility-restricted-border: var(--border-strong);
}
```

---

## 7. Supporting graphic language

### 7.1 The spark as a motif

The four-point spark may appear beyond the logo as a restrained system element, but its value comes from scarcity. Reserve it for:

- canonical, source, or reference significance
- rare branded moments — onboarding, empty states, major loading transitions
- restrained editorial punctuation
- tiny brand stamps

Do not use it for selection, hover, focus, or active state; map pins or locations; routine loading or progress; navigation; favorites/unread/new/pinned states; generic "featured" content; premium/paid status; or ordinary section dividers — these are conventional interface concerns and get conventional interface icons instead. See §17 for the full policy on the spark versus interface iconography.

Do not turn every bullet into a spark. Recognition comes from restraint.

### 7.2 Maps, graphs, and relationships

Lorenzo’s visual vocabulary should include:

- nodes
- paths
- relationship edges
- timelines
- coordinates
- locator pins
- nested worlds
- cards and records
- repository links
- knowledge visibility
- branching histories

These should look like **information architecture**, not treasure maps.

Use crisp line work, clear hierarchy, and modern labeling. See §18 for the concrete visual grammar — line styles, node states, and structural markers — that vocabulary resolves to.

### 7.3 Lines and borders

Preferred line character:

- thin to medium
- geometric
- slightly softened where appropriate
- low-contrast by default
- higher contrast only for active or selected structures

Avoid ornamental borders, etched frames, faux parchment edges, scrollwork, or medieval dividers.

### 7.4 Texture

Lorenzo is warm, but not textured by default.

Prefer flat Paper and Parchment fields over literal paper grain, leather, stone, wood, brass, or magical glow textures.

Illustration may contain richer materials; the product UI should not imitate them.

---

## 8. Layout and spatial system

### 8.1 General composition

Lorenzo should feel spacious enough to think in, but efficient enough to manage dense information.

Use a strong grid and consistent spacing. A practical base is an 8 px spacing system with 4 px half-steps where density requires.

Recommended rhythm:

- 4 px — micro spacing
- 8 px — related controls
- 16 px — normal component spacing
- 24 px — grouped content
- 32 px — section separation
- 48–64 px — major editorial breathing room

### 8.2 Cards and surfaces

Cards should resemble clean information records, not parchment panels.

Preferred:

- subtle borders
- the canonical radius for that surface (§8.3), never a nearby number
- clear title / metadata hierarchy
- calm neutral surfaces

Shadow policy is binary, not "little or no shadow": default surfaces — cards, panels, table rows — get a border and no shadow at all. Reserve shadow for genuinely elevated overlays: menus, dialogs, popovers, and drag previews, where it signals "this is floating above the page" rather than decorating a surface that already sits flat in the layout.

Avoid excessive glassmorphism, floating-card stacks, heavy skeuomorphic panels, or ornamental frames.

### 8.3 Radius

Canonical values — pick one of these, not a nearby number:

- controls (`--radius-control`): 8 px
- cards (`--radius-card`): 10 px
- large surfaces (`--radius-surface`): 16 px
- pills (`--radius-pill`): 999 px, only where the component is genuinely a tag, filter, or status token

A different radius is a deliberate, named exception, not a rounding choice — inconsistent radius is one of the invisible things that makes a multi-app suite feel unrelated.

The brand should not become bubbly.

### 8.4 Density

Dense data views should prioritize legibility over decorative branding.

When a screen contains tables, timelines, relationship graphs, permissions, or knowledge matrices, reduce brand decoration and let the structure do the work.

---

## 9. Mascot and illustration system

### 9.1 Lorenzo, the character

Lorenzo is the brand mascot and a personification of the product’s role as worldkeeper, archivist, navigator, and curious custodian of interconnected realities.

Established visual identifiers include:

- androgynous presentation
- sidecut hairstyle
- dark hair with blue tips or blue accents
- blue eyes
- contemporary, slightly scholarly styling
- a balance of archival and modern cues

Lorenzo should read as a person who maintains worlds, not as a fantasy wizard.

They may appear with books, maps, documents, stars, nodes, timelines, devices, repositories, diagrams, or other worldbuilding tools.

### 9.2 Catileo

Catileo is Lorenzo’s cat and a secondary mascot character.

Catileo adds warmth, quiet humor, domesticity, and contrast to Lorenzo’s careful worldkeeping role.

Catileo should remain supporting rather than becoming a competing brand mark. The cat may appear in onboarding, community illustrations, empty states, easter eggs, release art, and informal brand moments.

### 9.3 Mascot usage

Use Lorenzo for:

- onboarding
- welcome states
- empty states
- documentation introductions
- release announcements
- community posts
- educational content
- stickers and merch
- error pages where warmth is useful
- editorial brand storytelling

Do not use the mascot as:

- a replacement for the brand mark
- a favicon
- tiny app chrome
- a repeated avatar in every product panel
- a permanent decorative layer behind dense data

### 9.4 Illustration direction

Future Lorenzo illustrations should favor:

- clean, confident shapes
- readable silhouettes
- controlled detail
- contemporary styling
- restrained line work
- warm human expressions
- genre mixing
- blue accents as a recurring identifier

Show multiple genres when context allows. A single composition may include a castle, orbital station, modern apartment, detective file, alien world, family tree, and ordinary city map.

That mixture is intentional: Lorenzo contains worlds, not one genre.

### 9.5 Mascot emblem

`mascot_emblem.png` is a secondary badge, not the master logo.

It is appropriate for:

- stickers
- event collateral
- community branding
- merch
- Discord splash imagery
- social posts
- README or landing-page illustration

Keep it as high-resolution raster art. Do not mechanically vector-trace it.

If a vector mascot emblem is ever required, redraw it intentionally as a simplified flat illustration with fewer shapes and clear production constraints.

---

## 10. Photography and non-mascot imagery

Lorenzo does not require a photographic brand style, but if photography is used, prefer images that communicate:

- making
- thinking
- notes
- maps
- tables
- collaboration
- research
- archives
- spaces where stories are built

Avoid generic fantasy cosplay imagery as the default brand representation.

For screenshots and product imagery, show real information architecture and meaningful data relationships. The product itself is visually interesting; it does not need fantasy dressing.

---

## 11. Motion

Motion should feel like orientation and discovery, not spectacle.

### 11.1 Core motion principles

- purposeful
- calm
- precise
- short
- reversible where possible
- respectful of reduced-motion preferences

### 11.2 Brand-mark motion

This section governs the rare branded-loading-moment case only — application startup, first-run setup, a large import (§17) — not routine request/response waiting, which uses conventional spinners, skeletons, and progress bars instead.

The shaded spark is the preferred motion-capable mark for those rare moments because the fixed faux-lighting gives rotation and movement visual direction.

Appropriate loader treatments:

- slow continuous rotation of the whole shaded mark
- a restrained 96–102% scale pulse
- a subtle opacity breathe
- a brief highlight sweep achieved by animating overlay opacity, not by adding glow

Do not independently rotate the highlight or shade layers.

Suggested loader timing:

- continuous rotation: approximately 1.4–1.8 s per turn
- pulse: approximately 1.2–1.6 s ease-in-out
- short UI transitions: 150–220 ms
- larger panel or route transitions: 220–320 ms

For `prefers-reduced-motion`, replace rotation with a static mark or a minimal opacity change.

### 11.3 Mascot motion

If Lorenzo or Catileo are animated, keep motion characterful but subtle: blink, page turn, ear flick, small head movement, map line appearing, or a quiet nod.

Avoid perpetual bouncing, exaggerated squash-and-stretch, or game-like idle loops in serious product contexts.

---

## 12. Product expression by surface

### 12.1 Website

Use the horizontal light- or dark-background lockup in navigation.

Use the centered signature wordmark for major hero or formal brand moments.

Use the mascot selectively in onboarding, editorial, community, or explanatory sections.

Let product screenshots and structured content carry most of the visual weight.

### 12.2 Desktop and web app

Header / shell:

- horizontal lockup when room allows
- spark alone in compact navigation

UI:

- Geist-first typography
- Archive Blue interactions
- Gold sparingly for brand and special emphasis
- Newsreader for world/entity titles only when it improves character rather than density

Do not decorate every record with the mascot or star.

### 12.3 Mobile app

Use the spark as the identity anchor.

A future app icon should be built around the spark, not the wordmark or mascot emblem. Preferred direction: shaded Gold spark on Lorenzo Ink in a simple platform-appropriate container with generous optical padding.

Within the app, use the mark sparingly. The product should feel branded through color, typography, spacing, and tone rather than repeated logos.

### 12.4 Favicon

Use the standalone spark.

Preferred starting asset: unshaded colored mark or monochrome mark depending browser/theme requirements.

At 16 px, test the center aperture and arm weight optically. If a dedicated favicon variant is created, it may slightly enlarge the aperture or strengthen fragile geometry, but it must remain recognizably the same mark.

Do not use the mascot emblem as a favicon.

### 12.5 Discord bot

Avatar:

- spark or future contained app-icon treatment

Bot messages:

- `✧` may be used as a lightweight signature or section marker
- Lorenzo and Catileo may appear in welcome, help, celebration, or community content

Keep routine operational messages concise and product-like. The bot should not roleplay as the mascot unless that behavior is deliberately designed.

### 12.6 CLI

The CLI should be one of the cleanest expressions of the identity.

Preferred startup/header treatment when Unicode is supported:

```text
✧ Lorenzo
```

Optional ANSI treatment:

- `✧` in Medici Gold
- `Lorenzo` in the terminal’s normal foreground or a high-contrast neutral

Do not print large ASCII-art versions of the logo by default.

Use Geist Mono in rendered documentation and code examples.

### 12.7 Developer portal and API docs

Use the horizontal lockup in documentation navigation.

Use the spark alone for compact sidebar or favicon use.

Keep the developer experience visually quieter than marketing surfaces.

Code, schemas, IDs, and technical navigation should be Geist / Geist Mono first. Gold should be rare.

### 12.8 Social avatars

Use the spark or future contained app-icon treatment.

Use the mascot for posts and campaign imagery, not as the default tiny avatar unless the community intentionally centers the character.

### 12.9 Print and merchandise

Use monochrome assets for processes that require one color.

Use the mascot emblem for stickers and character-driven merch.

Use the spark alone for premium minimal items: pins, patches, notebook covers, embossing, foil, caps, or small stamps.

When using actual metallic foil or embroidery, simplify to the unshaded mark.

---

## 13. Brand architecture across a product suite

Lorenzo should scale to multiple products without fragmenting into mini-brands.

### 13.1 One master mark

All Lorenzo products share the same spark.

Do not recolor the spark by product to create artificial sub-brands.

If products need differentiation, use:

- product descriptors
- interface accent colors
- icons
- imagery
- navigation context

without altering the master identity.

### 13.2 Descriptor system

When a product name needs to appear beside the logo, set the descriptor in Geist Medium rather than extending the custom wordmark.

Example structure:

`[spark] Lorenzo   CLI`

`Lorenzo` remains the custom identity; `CLI` is functional information.

### 13.3 Product-specific illustrations

Different tools may emphasize different motifs:

- maps and topology
- relationships and knowledge
- timelines
- repositories
- character sheets
- synchronization
- developer automation

They should still share the core palette, typography, spacing logic, mark, and mascot world.

---

## 14. Voice and writing

Lorenzo sounds like a knowledgeable archivist, not a dungeon master.

### 14.1 Voice traits

Prefer:

- clear
- concise
- precise
- curious
- quietly playful
- human
- useful

Avoid:

- generic fantasy language
- fake epic grandeur
- excessive lore voice in functional UI
- corporate SaaS clichés
- over-cute mascot speech

Avoid phrases such as:

- “Embark on your adventure”
- “Forge your destiny”
- “Enter the realm”
- “Unlock the power of your imagination”

The product is already about worlds. The copy does not need to perform fantasy.

### 14.2 Example UI voice

Preferred:

> Your world is empty. Add a person, place, event, object, or whatever else exists here.

<!-- -->

> Only the GM knows this.

<!-- -->

> This character exists in three timelines.

<!-- -->

> No repository is connected yet.

<!-- -->

> Catileo appears to have misplaced this page.

The last example is appropriate for a rare mascot-led error state, not routine system copy.

### 14.3 Terminology

Prefer stable domain terms consistently. If Lorenzo distinguishes repositories, worlds, timelines, planes, entities, secrets, knowledge, campaigns, and visibility, each term should have a clear product definition.

Do not swap terminology for flavor from screen to screen.

---

## 15. Accessibility

Brand consistency never overrides accessibility.

### 15.1 Color

- maintain WCAG-appropriate text contrast
- do not use Gold as small body text on Paper
- do not use Astral Blue as ordinary small text on Paper without checking contrast
- do not rely on hue alone to communicate secret/public, selected/unselected, canonical/non-canonical, or error/success states

### 15.2 Logos

For meaningful logo images, use accessible names such as:

- `Lorenzo`
- `Lorenzo brand mark`

Decorative repeated logos should be hidden from assistive technology.

### 15.3 Mascot alt text

Describe what matters in context rather than exhaustively inventorying the illustration.

Example:

> Lorenzo reviewing an open atlas while Catileo sleeps on the pages.

If the image is purely decorative and nearby text already carries the meaning, use empty alt text.

### 15.4 Motion

Honor reduced-motion preferences.

Do not make loading identity dependent on spinning animation alone.

### 15.5 Type and density

Do not shrink typography to preserve a decorative layout. Dense data should remain readable, zoomable, and navigable.

### 15.6 Interface icons

An icon inside an already-labelled control is decorative and hidden from assistive technology:

```html
<button type="button">
  <svg class="icon" aria-hidden="true"><use href="/assets/icons/ui.svg#icon-save"></use></svg>
  Save
</button>
```

An icon-only control names the control, not the artwork inside it:

```html
<button type="button" aria-label="Copy">
  <svg class="icon" aria-hidden="true"><use href="/assets/icons/ui.svg#icon-copy"></use></svg>
</button>
```

Prefer visible text where practical. Use native `<button>`, `<a>`, `<details>`, and other semantic elements rather than making a bare SVG interactive. See §17 for the icon system itself.

---

## 16. Asset governance and implementation

### 16.1 Source of truth

The SVG assets listed in this document are the master production files for marks and lockups.

Do not recreate them from screenshots or PNG exports.

### 16.2 SVG principles

Maintain:

- named groups
- reusable geometry where appropriate
- viewBox-based scaling
- transparent backgrounds unless a contained icon explicitly requires a field
- real negative space in the spark center
- no embedded fonts in logo artwork
- no unnecessary metadata or editor-specific cruft

### 16.3 Raster exports

Generate PNG/WebP/AVIF derivatives from the SVG masters as needed.

Do not treat raster exports as the source of truth for logos.

Mascot imagery is the exception: the current mascot and mascot emblem are intentionally raster illustration masters.

`mascot_emblem_web.png` is one such derivative: `mascot_emblem.png` resized to 640px wide and palette-quantized for contexts (README hero art, chat/embed previews) where the 5016px master's file size would be wasteful. Regenerate it the same way if the master is ever redrawn.

`social_banner_github.png` is another: `social_banner.png` resized to exactly 1280×640 (GitHub's recommended social-preview size) and kept truecolor rather than palette-quantized, since quantizing introduced visible banding in the illustration's blurred-foliage depth-of-field — 256 colors is fine for the flat-shaded mascot emblem but not for soft gradients. Regenerate at 1280×640 truecolor if the master changes.

### 16.4 File naming

Keep naming descriptive and predictable.

Current convention:

`brand_mark_[variant].svg`

`wordmark_[variant].svg`

`lorenzo_horizontal_lockup_[variant].svg`

Recommended future patterns:

`app_icon_[platform-or-variant].svg`

`favicon_[size-or-variant].svg`

`mascot_[pose-or-context].png`

Avoid filenames such as `logo-final-final-2.svg`.

### 16.5 Versioning

Identity geometry should be versioned deliberately.

A color correction or export optimization is not necessarily a new identity version.

A change to the spark silhouette, wordmark letterforms, spacing, or lockup composition is a brand-system change and should be documented.

---

## 17. Icon and symbol strategy

The spark and interface icons are two separate systems, not one. §4 and §7.1 already narrowed the spark to identity and canonical/significant meaning; this section states that boundary explicitly and covers the ordinary interface iconography that fills every job the spark no longer does.

### 17.1 The Lorenzo spark

The four-point spark is Lorenzo's primary identity symbol. Its value comes from scarcity.

Use it for:

- Lorenzo identity: logo, favicon, app icon, brand stamp
- canonical, source, or reference significance
- rare branded transitions, onboarding, and empty states
- restrained editorial punctuation
- major branded loading moments (§11.2) — application startup, first-run setup, a large import

Do not use it for:

- selection, hover, focus, or active state
- generic map pins or locations
- routine loading or progress
- navigation
- favorites, unread, new, or pinned states
- generic importance or "featured" content
- premium/paid status
- ordinary section dividers
- a default placeholder for user- or entity-owned avatars/pictures

A spark inside product data should imply *this has special significance within Lorenzo*. It should never merely mean "currently selected" or "please wait" — use conventional UI treatments for transient state instead: color, borders, focus rings, checks, progress bars, skeletons, spinners, line styles, and standard icons.

### 17.2 Icon sources

- UI icons: [Tabler Icons](https://tabler.io/icons)
- External brand icons: official brand assets where required; otherwise [Simple Icons](https://simpleicons.org)
- Lorenzo-specific domain icons: Tabler first, custom only when necessary (§17.4)
- Self-host all icon assets. No CDN or hotlinking.
- Do not mix icon families casually.

Brand assets (§4, §16) and UI icons are separate systems with separate governance.

### 17.3 UI icons

Tabler is the default interface icon family. Use conventional symbols for conventional actions — save, copy, delete, search, edit, settings, map/location, visibility, lock, history, undo, expand/collapse, notifications. Prefer established visual language over novelty.

Use the standard Tabler visual grammar:

- 24×24 viewBox
- 2px stroke
- round caps and joins
- outline-first
- `currentColor`
- no baked-in theme colors

Do not vary stroke weight or mix filled/outline variants arbitrarily.

### 17.4 Custom domain icons

Create a custom icon only when Lorenzo has a genuine domain concept that Tabler cannot represent clearly — for example a repository/source relationship, prototype inheritance, timeline divergence, knowledge provenance, or world/plane semantics.

A custom icon should visually belong beside Tabler and follow the same geometry and stroke conventions. Keep Lorenzo-owned custom icons separate from third-party originals. The spark is a brand asset, not a fallback custom icon.

### 17.5 Semantic naming

Application-facing icon names describe meaning, not upstream artwork. Prefer `icon-delete`, `icon-private`, `icon-location`, `icon-warning`, `icon-history` over `icon-trash`, `icon-lock`, `icon-pin`, `icon-triangle`, `icon-clock`.

Maintain one semantic mapping from Lorenzo concepts to source icons. The same icon should not represent materially different concepts within the same context.

### 17.6 Runtime

Keep upstream SVG originals unchanged. Generate a local, same-origin SVG sprite from an explicit manifest containing only the icons actually used:

```yaml
copy: copy
delete: trash
private: lock
warning: alert-triangle
location: map-pin
```

Application markup uses the stable, Lorenzo-owned IDs from that manifest, not the upstream names directly:

```html
<svg class="icon" aria-hidden="true">
  <use href="/assets/icons/ui.svg#icon-copy"></use>
</svg>
```

Do not expose library names or versions in application markup. Fingerprint the generated sprite asset in production. See §15.6 for how icon-only and decorative icons get labelled.

### 17.7 Third-party brand marks

External brand marks (a payment provider's logo, a platform's logo) are not UI icons — store and govern them separately from `ui.svg`. Prefer official assets where a brand's own guidelines require them; Simple Icons may be used where appropriate, but its artwork does not grant blanket trademark permission. Do not recolor, modify, or combine a third-party brand mark unless that brand's own guidelines permit it.

### 17.8 State and status

Icons reinforce state; they do not define it. Use explicit text for success, warning, error, pending, private/restricted visibility, and canonical/source status — matching §15.1's "do not rely on hue alone" rule and §6.6's color-neutral visibility treatment.

Visibility is not severity: a private or GM-only item uses the neutral treatment plus a clear label and icon (§6.6), never danger styling. Selection and focus are UI states, not entity properties — represent them through surfaces, borders, and focus rings (§6.6), not an icon standing in for the state.

### 17.9 Loading

Use standard loading patterns for routine operations: spinner, skeleton, progress bar, or indeterminate progress. Reserve animated spark treatment for the rare branded transitions named in §17.1/§11.2 — the spark is for branded waiting, not routine waiting.

### 17.10 Principle

Use Lorenzo-specific visual language only where Lorenzo-specific meaning exists. Let ordinary interface mechanics remain ordinary. The quieter the system is around it, the more meaningful the spark becomes.

---

## 18. Information visualization grammar

§7.2 names the vocabulary — nodes, paths, timelines, coordinates, relationships, repository links, knowledge visibility, branching histories — and the standard it has to meet: information architecture, not treasure maps. That's the right direction, but on its own it's still direction rather than a system. Given what Lorenzo actually models, graphs, maps, and timelines may end up more characteristic of the product than the logo — so the vocabulary needs a concrete visual answer before much of that UI gets built, not a bespoke one invented per feature.

### 18.1 What needs a consistent visual answer

Each of these needs one recognizable treatment, reused everywhere it appears: node taxonomy, edge taxonomy, current selection, unknown/hidden state ([knowledge](../domain/entities-knowledge-and-visibility.md)), prototype-inherited state, canonical vs. local state ([repository provenance](../domain/repositories.md)), temporal divergence ([the timeline/plane/multiverse axes](../domain/world-model.md)), containment, and cross-world links.

Most of these don't need a unique color. Line style, shape, labels, and hierarchy carry more of the distinction than color does — color reinforces the grammar below, it isn't the grammar.

### 18.2 Core grammar

| Visual treatment            | Meaning                                                                                |
| --------------------------- | -------------------------------------------------------------------------------------- |
| Solid edge                  | Direct, explicit relationship                                                          |
| Dashed edge                 | Derived, inherited, or indirect relationship                                           |
| Dotted/faded edge           | Unknown, inferred, incomplete, or uncertain relationship                               |
| Arrowhead                   | Direction matters                                                                      |
| No arrowhead                | Symmetric / non-directional relationship                                               |
| Branch marker               | Timeline or history divergence                                                         |
| Merge marker                | Timelines or histories converge or reconcile                                           |
| Spark marker                | Canonical/source/reference point (§17.1 — never generic importance)                    |
| Lock icon                   | Restricted visibility, as a static badge (§6.6's visibility-restricted treatment)      |
| Eye / eye-off icon          | A show/hide control on the current view — a diagram layer or branch, not a domain fact |
| `--surface-selected` fill   | Current selection, optionally paired with `--focus-ring` when keyboard-focused         |
| Muted / low-opacity node    | Inactive, unavailable, out-of-context, or unresolved                                   |
| `--canonical` (Gold) accent | Canonical/reference significance only — never generic importance (§6.6)                |

Branch/merge markers start from Tabler's own `git-branch`/`git-merge` glyphs (§17.3) — reach for a custom mark (§17.4) only if that metaphor turns out not to read for a story timeline.

A few rules matter more than the exact mapping:

- **Selection stays separate from meaning.** A selected node gets `--surface-selected`/`--focus-ring`; its semantic shape or icon never changes to show selection.
- **Color reinforces meaning, it doesn't carry it.** "Inherited" should still read as inherited in grayscale — dash pattern, shape, labels, and icons carry the distinction first, matching §15.1's existing rule.
- **Edges carry relationship semantics; nodes carry entity semantics.** Don't turn every relationship into a different node color.

### 18.3 Keep the vocabulary small

Don't expect anyone to memorize twelve edge styles. Keep the core grammar to roughly three edge styles, two or three node states, the small set of structural markers above, and ordinary Tabler icons (§17.3). Anything more specialized than that gets a text label instead of a new visual convention.

The same restraint applies to node shape: resist building a shape ontology. Use a distinct shape only where it's structurally useful for reading the graph faster — not as decoration. If circles versus squares don't improve reading, don't add them just to add them.

### 18.4 One grammar across every view

The same primitives should carry across every surface that draws one of these, not a separate visual language per feature:

- **relationship graph** — direct vs. inherited relationships
- **timeline** — events, branches, convergence
- **repository/provenance** — source → derived → local copy
- **knowledge graph** — known, hidden, uncertain
- **world map** — ordinary locations vs. canonical/reference anchors

That consistency is the actual payoff: Lorenzo should have one recognizable way of saying direct, derived, uncertain, selected, restricted, and canonical — not a different visual language for every feature that happens to draw a graph.

---

## 19. Practical selection guide

Use this decision flow to pick the right *brand* asset. For an ordinary interface icon (delete, search, lock, and the like), this isn't it — see §17 instead.

### Need a full logo in a horizontal space?

- light background → `lorenzo_horizontal_lockup_light_bg.svg`
- dark background → `lorenzo_horizontal_lockup_dark_bg.svg`
- one-color production → `lorenzo_horizontal_lockup_monochrome.svg`

### Need a formal centered signature?

- use the appropriate `wordmark_*` asset
- use `wordmark_full.svg` when the full signature composition is specifically desired

### Need the brand mark at a small size?

- use `brand_mark.svg` or `brand_mark_monochrome.svg`
- prefer unshaded at very small sizes

### Need a richer standalone mark?

- use `brand_mark_shaded.svg`
- use `brand_mark_shaded_monochrome.svg` in single-color contexts

### Need personality rather than identity?

- use `mascot.png`
- use `mascot_emblem.png` for a badge-like community or merch expression

### Need plain text only?

- use `✧ Lorenzo`

---

## 20. Quick do / do not

### Do

- use the spark consistently
- keep Gold restrained
- let blue carry interaction and mascot continuity
- use the custom wordmark as artwork
- use modern UI typography around the historic-feeling wordmark
- show multiple genres in brand imagery
- use the mascot for warmth and storytelling
- use whitespace and hierarchy before decoration
- use the correct light/dark lockup asset
- simplify as the available size decreases
- use Tabler-based interface icons for ordinary interface concerns (§17)

### Do not

- turn Lorenzo into a fantasy-only brand
- add shields, crests, scrolls, runes, or generic compass roses
- overuse stars throughout the UI
- use the spark for selection, loading, navigation, or status — that's what interface icons are for (§17)
- make Gold the dominant interface color
- typeset the wordmark from a font
- use the mascot as the tiny primary logo
- auto-trace the mascot emblem
- create separate logo marks for each product
- add gradients or chrome effects to the spark
- let brand decoration reduce product clarity

---

## 21. Mascot

Lorenzo the mascot is described in detail in [the lorenzo charcter bible](lorenzo-character-bible.md)

The second mascot, Catileo, is described in [the catileo character bible](catileo-character-bible.md)

---

## 22. One-line summary

**Lorenzo is a modern system for keeping track of worlds, expressed through scholarly typography, calm information design, blue interaction, restrained gold punctuation, a distinctive four-point spark, and the human warmth of Lorenzo and Catileo.**
