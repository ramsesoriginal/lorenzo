import type { BulkResultItem, ItemInstance } from './types';

// The board page (src/pages/board/index.astro) wires all of this to real DOM
// elements and to lib/items.ts's real network calls - kept here, DOM-free,
// so the decision logic actually at risk of a silent bug (which give path
// to take, how a never-all-or-nothing bulk result gets summarized, one-slot
// undo's own state machine) is unit-testable without a browser.

// --- Undo ---

// One-slot undo, mirroring apps/loot-bot's own convention (ADR 0068): each
// new undoable action overwrites whatever was pending, not a stack - this
// is "I just made a mistake," not a history browser. Bulk actions and
// deletes are deliberately not undoable - a multi-item reversal needs
// per-item previous state, and a deleted instance's id is simply gone.
export type UndoPayload =
  | {
      kind: 'restore-owner';
      entityId: string;
      previousOwnerId: string | null;
      /** Given when the give handed it over too (ADR 0115): where it was before. */
      previousContainerId?: string | null;
    }
  | { kind: 'restore-container'; entityId: string; previousContainerId: string | null }
  | {
      kind: 'undo-merge';
      intoEntityId: string;
      quantity: number;
      previousOwnerId: string | null;
    }
  | { kind: 'undo-split'; splitOffEntityId: string; intoEntityId: string };

export interface UndoActions {
  setOwner(tenantId: string, entityId: string, ownerCharacterId: string): Promise<unknown>;
  unsetOwner(tenantId: string, entityId: string): Promise<unknown>;
  setContainer(tenantId: string, entityId: string, containerEntityId: string): Promise<unknown>;
  clearContainer(tenantId: string, entityId: string): Promise<unknown>;
  splitItemInstance(
    tenantId: string,
    entityId: string,
    quantity: number,
    ownerCharacterId?: string,
  ): Promise<unknown>;
  mergeItemInstance(tenantId: string, entityId: string, intoEntityId: string): Promise<unknown>;
}

const DEFAULT_UNDO_TTL_MS = 5 * 60 * 1000;

// The controller owns only the pending-payload state machine (what's
// pending, its expiry timer, and mapping a payload to the API call(s) that
// reverse it) - showing/hiding the undo banner and reloading the board
// stay the page's own job, driven by the callbacks passed to record()/
// apply() below, the same separation lib/beingPicker.ts's onDone already
// establishes for its own panels.
export function createUndoController(
  tenantId: string,
  actions: UndoActions,
  ttlMs = DEFAULT_UNDO_TTL_MS,
) {
  let pending: UndoPayload | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  function record(payload: UndoPayload, onExpire: () => void): void {
    pending = payload;
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      pending = null;
      onExpire();
    }, ttlMs);
  }

  function clear(): void {
    pending = null;
    clearTimeout(timeoutId);
  }

  function getPending(): UndoPayload | null {
    return pending;
  }

  async function restoreContainer(entityId: string, previousContainerId: string | null) {
    if (previousContainerId) {
      await actions.setContainer(tenantId, entityId, previousContainerId);
    } else {
      await actions.clearContainer(tenantId, entityId);
    }
  }

  // Throws on failure - the caller (the board page) decides how to surface
  // that (showTransientError) and whether to reload. Succeeds silently;
  // the caller reloads on its own success path.
  async function apply(): Promise<void> {
    const payload = pending;
    if (!payload) return;
    pending = null;
    clearTimeout(timeoutId);
    switch (payload.kind) {
      case 'restore-owner':
        if (payload.previousOwnerId) {
          await actions.setOwner(tenantId, payload.entityId, payload.previousOwnerId);
        } else {
          await actions.unsetOwner(tenantId, payload.entityId);
        }
        if (payload.previousContainerId !== undefined) {
          await restoreContainer(payload.entityId, payload.previousContainerId);
        }
        break;
      case 'restore-container':
        await restoreContainer(payload.entityId, payload.previousContainerId);
        break;
      case 'undo-merge':
        // The merged-away instance's id is gone - this recreates an
        // equivalent split-off stack rather than literally restoring the
        // original, an accepted approximation (same one apps/loot-bot's
        // own undo-merge documents).
        await actions.splitItemInstance(
          tenantId,
          payload.intoEntityId,
          payload.quantity,
          payload.previousOwnerId ?? undefined,
        );
        break;
      case 'undo-split':
        await actions.mergeItemInstance(tenantId, payload.splitOffEntityId, payload.intoEntityId);
        break;
    }
  }

  return { record, clear, getPending, apply };
}

// --- Give ---

// The riskiest branch in "give to…": giving fewer than the full stack
// delegates to bulk-assign's own split-with-owner (ADR 0044) instead of a
// plain ownership transfer, since a plain setOwner would hand over the
// *whole* stack regardless of what was typed. `quantity === item.quantity`
// (or blank/0) means "give all of it" - the plain-transfer path, not a
// split that would leave a zero-quantity remainder behind.
export type GivePlan = { mode: 'partial'; quantity: number } | { mode: 'whole' };

export function planGive(
  item: { quantity: number | null },
  requestedQuantity: number | undefined,
): GivePlan {
  if (requestedQuantity && item.quantity && requestedQuantity < item.quantity) {
    return { mode: 'partial', quantity: requestedQuantity };
  }
  return { mode: 'whole' };
}

// --- Bulk results (never all-or-nothing, ADR 0044/0065) ---

export interface BulkOutcome {
  succeededCount: number;
  failedCount: number;
  // Every entry failed - nothing changed server-side, so the caller can
  // safely treat this as a total failure (e.g. throw, leaving its panel
  // open for retry) rather than falling through to a reload.
  allFailed: boolean;
}

export function summarizeBulkResults(results: BulkResultItem[]): BulkOutcome {
  const failedCount = results.filter((r) => r.status === 'error').length;
  return {
    succeededCount: results.length - failedCount,
    failedCount,
    allFailed: results.length > 0 && failedCount === results.length,
  };
}

export function failedEntityIds(results: BulkResultItem[]): Set<string> {
  return new Set(results.filter((r) => r.status === 'error').map((r) => r.entity_id));
}

// --- Merge candidates ---

// Two instances are the "same kind of item" for merge purposes if they
// share the same set of direct prototypes - title alone isn't reliable,
// since ADR 0067's title-fallback-to-entity-name means two entirely
// unrelated catalog items can display the same text. The merge endpoint
// itself only checks same-container/same-owner (apps/api's
// item_instances.merge_item_instance), not item identity, so this filter
// is the only thing standing between a title collision and silently
// combining two different items' quantities.
export function samePrototypes(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const bIds = new Set(b);
  return a.every((id) => bIds.has(id));
}

export function findMergeCandidates(
  items: Iterable<ItemInstance>,
  target: ItemInstance,
): ItemInstance[] {
  return [...items].filter(
    (other) =>
      other.entity_id !== target.entity_id &&
      other.title === target.title &&
      samePrototypes(other.prototype_ids, target.prototype_ids),
  );
}
