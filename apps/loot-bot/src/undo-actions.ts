import { deletePendingUndo, getPendingUndo, setPendingUndo } from "./db.js";
import type { LorenzoApiClient } from "./lorenzo-client.js";

/**
 * Self-service undo (ADR 0068) - one row per Discord user
 * (`pending_undo`, db-schema.ts), overwritten by each new undoable action,
 * not a history/stack. `give`/`reassign`/`move`/`rename`/`merge` each
 * record enough state here to reverse themselves after a successful
 * write; `/confiscate` never does - a destroyed instance's id is gone, so
 * there is no real inverse, only "create a new one," which isn't honest
 * to call "undo."
 */

// How long a recorded action stays undoable - short on purpose, this is
// "I just made a mistake," not a long-lived history.
const TTL_MS = 5 * 60 * 1000;

export type UndoPayload =
  | { kind: "restore-owner"; entityId: string; previousOwnerCharacterId: string }
  | { kind: "restore-container"; entityId: string; previousContainerEntityId: string | null }
  | { kind: "restore-name"; entityId: string; previousTitle: string | null }
  | { kind: "undo-merge"; intoEntityId: string; quantity: number; ownerCharacterId: string | null };

/** Records the caller's one undoable action, replacing whatever was there
 * before (matching `pending_undo`'s own one-row-per-user primary key). */
export async function recordUndo(discordUserId: string, payload: UndoPayload): Promise<void> {
  await setPendingUndo(discordUserId, {
    actionType: payload.kind,
    payload: JSON.stringify(payload),
  });
}

export type UndoOutcome =
  | { kind: "none" }
  | { kind: "expired" }
  | { kind: "undone"; description: string };

/**
 * Reads, applies, and clears the caller's own pending undo, if any.
 * Always clears the row on the way out (found or not, expired or not) -
 * a failed or already-stale attempt shouldn't leave something a later
 * retry might apply against outdated state.
 *
 * `undo-merge` is the one approximate case: the original, merged-away
 * instance's id is gone (the merge deleted it), so this recreates a new
 * split-off instance with the same quantity/owner rather than literally
 * restoring the original - an accepted, documented approximation (see
 * ADR 0068), not a perfect inverse.
 */
export async function applyPendingUndo(
  client: LorenzoApiClient,
  tenantId: string,
  discordUserId: string,
  accessToken: string,
): Promise<UndoOutcome> {
  const row = await getPendingUndo(discordUserId);
  if (!row) return { kind: "none" };
  await deletePendingUndo(discordUserId);

  if (Date.now() - row.createdAt.getTime() > TTL_MS) {
    return { kind: "expired" };
  }

  const payload = JSON.parse(row.payload) as UndoPayload;
  switch (payload.kind) {
    case "restore-owner": {
      const restored = await client.setItemInstanceOwner(
        tenantId,
        payload.entityId,
        payload.previousOwnerCharacterId,
        accessToken,
      );
      return { kind: "undone", description: `Gave ${restored.title ?? "(untitled)"} back.` };
    }

    case "restore-container": {
      if (payload.previousContainerEntityId === null) {
        return {
          kind: "undone",
          description:
            "That item had no container before - nothing more this bot can undo automatically; move it back by hand if needed.",
        };
      }
      const restored = await client.setItemInstanceContainer(
        tenantId,
        payload.entityId,
        payload.previousContainerEntityId,
        accessToken,
      );
      return { kind: "undone", description: `Moved ${restored.title ?? "(untitled)"} back.` };
    }

    case "restore-name": {
      const restored = await client.renameItemInstance(
        tenantId,
        payload.entityId,
        payload.previousTitle ?? "(untitled)",
        accessToken,
      );
      return { kind: "undone", description: `Renamed back to ${restored.title ?? "(untitled)"}.` };
    }

    case "undo-merge": {
      const { data: restored } = await client.splitItemInstance(
        tenantId,
        payload.intoEntityId,
        payload.quantity,
        accessToken,
        undefined,
        payload.ownerCharacterId ?? undefined,
      );
      return {
        kind: "undone",
        description: `Split ${payload.quantity} back out as ${restored.title ?? "(untitled)"} - the merge itself can't be perfectly reversed, so this recreates a separate stack rather than restoring the original.`,
      };
    }

    default: {
      const exhaustive: never = payload;
      throw new Error(`unknown undo payload kind: ${JSON.stringify(exhaustive)}`);
    }
  }
}
