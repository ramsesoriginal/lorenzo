import type { Board } from '../../lib/boardColumns';
import type { EntitySummary, ItemInstance } from '../../lib/types';

// What the board shows right now, shared by its parts and read by the item dialog.
export type BoardState = {
  // entity_id -> its instance, for every card rendered.
  items: Map<string, ItemInstance>;
  // Every column a card can be dropped into, by container: "Move to…"'s candidates.
  containers: Map<string, EntitySummary>;
  // Containers whose column lists something: what "Give what's inside…" is for.
  occupied: Set<string>;
  // Cards in a read-only column (ADR 0131): not dragged, and not moved from there.
  readOnly: Set<string>;
  // The being whose board this is, who carries what's in no container of theirs (ADR 0115).
  // Null on a group's board (ADR 0124) and on the board of unowned things.
  ownerId: string | null;
  current: Board | null;
};

export function createBoardState(): BoardState {
  return {
    items: new Map(),
    containers: new Map(),
    occupied: new Set(),
    readOnly: new Set(),
    ownerId: null,
    current: null,
  };
}

// The container an item is in, if any. Its owner carrying it isn't one (ADR 0115).
export function containerOf(
  state: BoardState,
  item: ItemInstance,
): { id: string; name: string } | null {
  const id = item.container_entity_id;

  // In its owner's hands, or the board's being's, it's in no container of theirs.
  if (!id || id === item.owner_entity_id || id === state.ownerId) return null;

  return state.containers.get(id) ?? { id, name: 'container' };
}
