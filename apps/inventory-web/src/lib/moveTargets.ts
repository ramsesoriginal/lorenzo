import type { EntitySummary, ItemInstance } from './types';

export interface MoveTarget {
  id: string;
  name: string;
}

// Candidates for the item detail dialog's "Move to…" button - the
// non-drag-and-drop fallback for a single-item container move (drag-and-
// drop was previously the only way, board/index.astro's bindDropZone).
// Sourced entirely from data the board already has in hand, the same
// "candidates already visible on the current board" convention
// findMergeCandidates/detailMergeButton already established, rather than
// a new search endpoint:
//
// - every container currently rendered as its own board column
//   (`containers` - a container only gets a column once it's occupied,
//   ADR 0020's own "one group per occupied container"), and
// - every card on the board flagged `is_container` (ADR 0066), including
//   one that's currently empty and so has no column of its own yet - the
//   common "move this into that empty backpack" case a columns-only list
//   would otherwise never offer.
//
// Always excludes the item's own current container (drag-and-drop already
// no-ops a drop back onto the same column) and the item itself (an item
// can't be moved into itself).
export function collectMoveTargets(
  item: ItemInstance,
  containers: Iterable<EntitySummary>,
  boardItems: Iterable<ItemInstance>,
): MoveTarget[] {
  const seen = new Set<string>();
  const targets: MoveTarget[] = [];

  function add(id: string, name: string) {
    if (id === item.entity_id) return;
    if (id === item.container_entity_id) return;
    if (seen.has(id)) return;
    seen.add(id);
    targets.push({ id, name });
  }

  for (const container of containers) {
    add(container.id, container.name);
  }
  for (const candidate of boardItems) {
    if (candidate.is_container) {
      add(candidate.entity_id, candidate.title);
    }
  }
  return targets;
}
