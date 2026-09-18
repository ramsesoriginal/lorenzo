# 0080 - account-hub: CSS conventions, shared DOM helpers, page decomposition

Status: accepted

## Context

Engineering cleanup requested directly (not proposed as an open design question), covering three related things noticed while building RFC 0014: real duplication between `characters.astro` and `beings.astro`, `tenants.astro` growing large as more admin actions land on it, and markup that has grown ahead of its CSS.

Checked before deciding anything: this app already has no scoped `<style>` blocks and no inline styles anywhere - the Foundation slice (ADR 0071) forked `apps/inventory-web`'s already-correct ITCSS-style structure (`normalize.css` → `tokens.css` → `base.css` → `layout.css` → `components.css`, one entry point). The actual gap is narrower than "migrate away from scoped styles" - it's that four classes used in markup (`campaign-meta`, `campaign-subsection`, `notification-meta`, `tenant-role`) were never given rules in `components.css`, and several `<section>`/`<li>`/`<button>` structures added since Foundation have no class at all to hook a rule onto.

## Decision

### CSS: define the missing classes now, and require one going forward

The four undefined classes above get real rules in `components.css`, alongside the existing `.tenant-card`/`.item-card`/etc. conventions already there. Going forward, any new structural element introduced by RFC 0017's work gets a real, purpose-named class in the same file - no new element ships without one, closing the gap rather than letting it recur.

### Shared DOM helpers: `src/lib/dom.ts`

Two functions lift out identical logic currently duplicated verbatim between `characters.astro` (`renderCharacterItem`/`renderCreateForm`) and `beings.astro` (`renderBeingItem`/`renderCreateForm`) - both call the exact same `updateCharacter(tenantId, entityId, { name })`/`createCharacter` underneath, differing only in surrounding copy:

```ts
export function createStatusSpan(): HTMLSpanElement
export function renderRenameableItem(name: string, onRename: (newName: string) => Promise<void>): HTMLLIElement
export function renderCreateForm(placeholder: string, buttonLabel: string, onCreate: (name: string) => Promise<void>): HTMLFormElement
```

`renderRenameableItem` returns the `<li>` with name/rename-button/status already attached - callers `.append()` anything extra (the being handoff button, for instance) rather than the helper needing to know about every page's own extra actions. Not placed alongside `format.ts`'s dependency-free set - these build real DOM and call real API functions, so there's no import-chain purity to protect the way `format.ts`'s pure helpers needed.

### `tenants.astro` decomposition: incremental, not a standalone pass

Rather than refactor `tenants.astro` into pieces now and then immediately grow it again for RFC 0017's tenant-creation/membership/activity-log/notification additions, the split happens *as* each of those lands: `src/lib/campaignAdminUi.ts` (campaign create + edit, already-existing code moved as part of this ADR) and `src/lib/gmAndPlayerUi.ts` (GM management + invite-player panel, likewise moved now); `src/lib/membershipAdminUi.ts` and any notification-composer/activity-log module are added fresh when those RFC 0017 sub-slices are actually built, not stubbed out ahead of time. `userPicker.ts` (ADR 0074) already established this exact pattern - a `lib/*.ts` module that builds and returns DOM, not just an API wrapper - so this isn't a new kind of file, just more of an existing one.

## Consequences

- `characters.astro`/`beings.astro` both shrink to page-specific orchestration (`load()`, `renderCampaignSection`/`renderTenantSection`, the top-level auth check) plus calls into the shared helpers.
- `tenants.astro` shrinks now (campaign create/edit and GM/invite panels move out) and gains new, equally-sized modules rather than one larger file, as RFC 0017 proceeds.
- No behavior change - this is pure internal reorganization plus CSS additions, verified by the existing Playwright smoke tests (which check rendered pages settle correctly) continuing to pass unmodified.
