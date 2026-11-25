import type { Board } from '../../lib/boardColumns';
import type { EntitySummary, ItemInstance } from '../../lib/types';

// What changed on a card or two, as the server confirmed it: the board says it where it is, without
// being fetched or drawn again. Anything it can't place (a card that isn't on it) makes it say no.
export type BoardPatch = {
  // Names of beings, for the owner marks of what was given to them.
  owners?: [id: string, name: string][];
  // Cards that stay where they are, with some of what they say changed.
  updated?: { id: string; patch: Partial<ItemInstance> }[];
  // New cards, each right after one that is on the board.
  added?: { after: string; item: ItemInstance }[];
  // Cards that are gone (merged into another).
  removed?: string[];
};

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
  // The library's `unsorted` item, which marks a card as a placeholder (ADR 0238); null if it has
  // none, or it couldn't be found, and then no card is marked.
  unsortedId: string | null;
  current: Board | null;
};

export function createBoardState(): BoardState {
  return {
    items: new Map(),
    containers: new Map(),
    occupied: new Set(),
    readOnly: new Set(),
    ownerId: null,
    unsortedId: null,
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
