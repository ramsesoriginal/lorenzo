# Lorenzo — Brand Identity

version: 1.0
status: living specification
updated: 2026-09-09
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
| `mascot.png`                               | Lorenzo mascot illustration            | onboarding, product illustration, social, editorial |

Treat SVG files as the preferred production masters for marks and lockups. Keep the mascot artwork as high-resolution raster artwork unless a deliberate simplified vector redraw is commissioned. Do not auto-trace the mascot illustration into a large, noisy SVG.

### 4.2 Logo hierarchy

#### Primary product lockup

Use the horizontal lockup for most product and interface contexts:

`✧ Lorenzo`

This is the preferred header, navigation, documentation, product-shell, developer-portal, and partner-placement expression.

#### Signature wordmark

Use the centered wordmark with the supporting spark for moments where vertical room exists and the brand is the focal point: landing-page heroes, title screens, press pages, posters, cover pages, presentation openings, and formal brand moments.

#### Brand mark alone

Use the spark alone when space is constrained or recognition is already established: favicon, app icon basis, avatar, loading indicator, UI brand stamp, launcher icon, social avatar, watermark, selected product state.

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

#### Editorial and display — Instrument Serif

Use **Instrument Serif** selectively for:

- large campaign or world titles
- landing-page headlines
- editorial section titles
- narrative introductions
- empty-state titles
- selected entity names where a literary tone is useful

Do not use it for dense forms, long tables, small metadata, or developer tooling.

Fallback stack:

`"Instrument Serif", Georgia, "Times New Roman", serif`

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
| Hero display | Instrument Serif          |     48–72 px | Regular        |
| H1           | Instrument Serif or Geist |     36–48 px | Regular / 600  |
| H2           | Geist                     |     28–36 px | 600            |
| H3           | Geist                     |     20–24 px | 600            |
| Entity title | Instrument Serif          |     24–32 px | Regular        |
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

| Name             | Hex       | Role                                                |
| ---------------- | --------- | --------------------------------------------------- |
| **Lorenzo Ink**  | `#08131F` | primary text, logo, dark UI, deep surfaces          |
| **Archive Blue** | `#1769C2` | primary interaction color, links, active states     |
| **Astral Blue**  | `#3B91E8` | highlights, illustrative accents, selected details  |
| **Medici Gold**  | `#B88A3B` | brand mark, special accents, meaningful punctuation |
| **Parchment**    | `#F4EFE5` | warm editorial surfaces, illustration fields        |
| **Paper**        | `#FBFAF7` | primary light background                            |
| **Burgundy**     | `#7B2638` | rare secondary accent, secrets, dramatic emphasis   |

### 6.2 Palette logic

**Ink + Paper** provide the foundation.

**Archive Blue** provides interaction.

**Medici Gold** provides identity.

**Astral Blue** provides visual energy and connects the system to the mascot’s blue details.

**Parchment** adds warmth without resorting to literal parchment textures.

**Burgundy** is a controlled secondary accent, not a second primary brand color.

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

### 6.6 Design-token starter

```css
:root {
  --lorenzo-ink: #08131f;
  --lorenzo-archive-blue: #1769c2;
  --lorenzo-astral-blue: #3b91e8;
  --lorenzo-gold: #b88a3b;
  --lorenzo-parchment: #f4efe5;
  --lorenzo-paper: #fbfaf7;
  --lorenzo-burgundy: #7b2638;

  --lorenzo-bg: var(--lorenzo-paper);
  --lorenzo-fg: var(--lorenzo-ink);
  --lorenzo-action: var(--lorenzo-archive-blue);
  --lorenzo-brand-accent: var(--lorenzo-gold);
}

[data-theme="dark"] {
  --lorenzo-bg: var(--lorenzo-ink);
  --lorenzo-fg: var(--lorenzo-paper);
  --lorenzo-action: var(--lorenzo-astral-blue);
  --lorenzo-brand-accent: var(--lorenzo-gold);
}
```

---

## 7. Supporting graphic language

### 7.1 The spark as a motif

The four-point spark may appear beyond the logo as a restrained system element.

Appropriate uses:

- canonical or featured status
- selected nodes
- small dividers
- premium or special-but-not-monetized moments
- empty-state emphasis
- map anchors
- subtle section separators
- loading and progress
- tiny brand stamps

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

Use crisp line work, clear hierarchy, and modern labeling.

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
- restrained radius
- little or no shadow
- clear title / metadata hierarchy
- calm neutral surfaces

Avoid excessive glassmorphism, floating-card stacks, heavy skeuomorphic panels, or ornamental frames.

### 8.3 Radius

A useful starting system:

- controls: 6–8 px
- cards: 8–12 px
- large marketing surfaces: 12–20 px
- pills only where the component is genuinely a tag, filter, or status token

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

The shaded spark is the preferred motion-capable mark because the fixed faux-lighting gives rotation and movement visual direction.

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
- Instrument Serif for world/entity titles only when it improves character rather than density

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

## 17. Practical selection guide

Use this decision flow:

### Need a full logo in a horizontal space?

- light background → `lorenzo_horizontal_lockup_light_bg.svg`
- dark background → `lorenzo_horizontal_lockup_dark_bg.svg`
- one-color production → `lorenzo_horizontal_lockup_monochrome.svg`

### Need a formal centered signature?

- use the appropriate `wordmark_*` asset
- use `wordmark_full.svg` when the full signature composition is specifically desired

### Need a small icon?

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

## 18. Quick do / do not

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

### Do not

- turn Lorenzo into a fantasy-only brand
- add shields, crests, scrolls, runes, or generic compass roses
- overuse stars throughout the UI
- make Gold the dominant interface color
- typeset the wordmark from a font
- use the mascot as the tiny primary logo
- auto-trace the mascot emblem
- create separate logo marks for each product
- add gradients or chrome effects to the spark
- let brand decoration reduce product clarity

---

## 19. Mascot

This section is a placeholder for a future dedicated mascot specification.

### Lorenzo

**Role:** primary mascot and personification of the product.

**Core concept:** an androgynous worldkeeper / archivist / navigator who comfortably moves between books, maps, data, stories, timelines, and entire realities.

**Established visual anchors:** sidecut; dark hair with blue tips/accents; blue eyes; contemporary scholarly styling; confident, relaxed demeanor.

**Personality direction:** curious, composed, perceptive, slightly mischievous, capable, warm, never pompous.

**Brand function:** makes Lorenzo human; carries illustration, onboarding, community, educational, release, and storytelling moments that would be too expressive for the core mark.

Future mascot work should define:

- canonical outfit and alternate outfits
- age range / presentation guidance
- proportions and silhouette
- facial-expression library
- pose library
- color references
- recurring props
- illustration simplification levels
- animation behavior
- voice boundaries, if Lorenzo ever speaks in-product
- representation rules across genres and settings

### Catileo

**Role:** secondary mascot and Lorenzo’s cat.

**Core concept:** a quiet companion whose presence adds warmth, domesticity, occasional mischief, and visual contrast to Lorenzo’s careful worldkeeping.

**Brand function:** supporting character, easter egg, community favorite, occasional error-state or empty-state personality.

Future mascot work should define:

- canonical markings and silhouette
- scale relative to Lorenzo
- behavioral traits
- recurring poses
- when Catileo may appear alone
- boundaries on anthropomorphism

Until that work is complete, keep both characters visually consistent with the existing mascot art and avoid introducing conflicting canonical traits.

---

## 20. Future identity work

The current identity is sufficient to operate as a complete brand system.

Future work should focus on application rather than inventing additional logos.

High-value next assets may include:

- contained app icon based on the shaded spark
- optically tuned favicon variant for 16 px and 32 px
- product-descriptor lockup rules for CLI / Bot / API / Mobile
- iconography library
- mascot character sheet
- Catileo character sheet
- illustration simplification levels
- social templates
- presentation templates
- documentation theme tokens
- motion prototypes for the shaded spark loader
- print / embroidery simplification tests

Do not create additional primary marks unless a genuine functional need appears.

---

## 21. Brand checksum

When reviewing a new Lorenzo surface, ask:

1. Does it feel like a tool for maintaining worlds rather than a fantasy-themed tool?
2. Is the interface modern and legible, with the historical character reserved for identity and editorial moments?
3. Is the spark recognizable and used with restraint?
4. Is Gold punctuation rather than wallpaper?
5. Does the mascot add personality without becoming the interface itself?
6. Would this still feel like Lorenzo if the fantasy-specific content were replaced by science fiction, history, or contemporary fiction?
7. Does the design remain useful at the actual size and context where it will appear?
8. Is this part of one coherent Lorenzo ecosystem rather than a new mini-brand?

If the answer is yes across those questions, the identity is probably being applied correctly.

---

## 22. One-line summary

**Lorenzo is a modern system for keeping track of worlds, expressed through scholarly typography, calm information design, blue interaction, restrained gold punctuation, a distinctive four-point spark, and the human warmth of Lorenzo and Catileo.**
