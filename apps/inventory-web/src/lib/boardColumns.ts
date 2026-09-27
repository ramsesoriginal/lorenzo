// The board's columns (ADR 0123): what a being holds, as a row of what it
// carries - its own Equipped column first, always - and a row of what's held
// elsewhere; or, on the board of unowned things, one row as before (ADR 0077).
// Pure, so the order and the wording are tested without a page.
import type {
  EntitySummary,
  HeldByResponse,
  HeldGroup,
  ItemInstance,
  OwnedByResponse,
} from './types';

export interface BoardColumn {
  /** Unique on the board: the container's id, or 'loose' for things in none. */
  key: string;
  /** Where a card dropped here goes; null takes it out of every container. */
  dropTarget: string | null;
  title: string;
  /** Where the column's container is, when that's worth saying. */
  note: string | null;
  /** What the column says when nothing's in it. */
  empty: string;
  items: ItemInstance[];
}

const EMPTY_CONTAINER = 'This container is empty.';

export interface Board {
  carried: BoardColumn[];
  elsewhere: BoardColumn[];
  /** Owner names by id, to mark what isn't the board's being's own. */
  owners: Map<string, string>;
  /** The board's being; null on the board of unowned things. */
  holderId: string | null;
}

/** "in Carriage, in Stable": a container's surroundings, nearest first. */
function within(path: EntitySummary[]): string {
  return path.map((p) => `in ${p.name}`).join(', ');
}

function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function column(group: HeldGroup): BoardColumn {
  const { container, path } = group;
  let note: string | null = path.length > 0 ? capitalized(within(path)) : null;
  if (group.container_kind === 'being') {
    note = `${container.name} has these${path.length > 0 ? `, ${within(path)}` : ''}`;
  }
  return {
    key: container.id,
    dropTarget: container.id,
    title: container.name,
    note,
    empty: EMPTY_CONTAINER,
    items: group.item_instances,
  };
}

/** A being's board, from what it holds. */
export function heldBoard(response: HeldByResponse): Board {
  const [own, ...rest] = response.groups;
  if (!own) throw new Error("A held-by answer always starts with its holder's own group.");
  const equipped: BoardColumn = {
    key: own.container.id,
    // Dropping on it puts a card into the being, who carries it (ADR 0115).
    dropTarget: own.container.id,
    title: own.container_kind === 'being' ? 'Equipped' : own.container.name,
    note: null,
    empty: own.container_kind === 'being' ? 'Nothing equipped.' : 'Nothing here.',
    items: own.item_instances,
  };
  return {
    carried: [equipped, ...rest.filter((g) => g.carried).map(column)],
    elsewhere: rest.filter((g) => !g.carried).map(column),
    owners: new Map(response.owners.map((o) => [o.id, o.name])),
    holderId: own.container.id,
  };
}

/** The board of unowned things: what's in no container reads first. */
export function unownedBoard(response: OwnedByResponse): Board {
  const ordered = [...response.groups].sort((a, b) =>
    a.container === null ? -1 : b.container === null ? 1 : 0,
  );
  return {
    carried: ordered.map((g) => ({
      key: g.container?.id ?? 'loose',
      dropTarget: g.container?.id ?? null,
      title: g.container?.name ?? 'Unowned',
      note: null,
      empty: g.container ? EMPTY_CONTAINER : 'Nothing here.',
      items: g.item_instances,
    })),
    elsewhere: [],
    owners: new Map(),
    holderId: null,
  };
}

/**
 * Whose an item is, when it isn't the board's being's own: "Pia's", or "No one's" for an
 * unowned item. Null for the being's own things, and on the board of unowned things.
 */
export function ownerMark(item: ItemInstance, board: Board): string | null {
  if (board.holderId === null || item.owner_entity_id === board.holderId) return null;
  if (item.owner_entity_id === null) return "No one's";
  const name = board.owners.get(item.owner_entity_id);
  return name ? `${name}'s` : "Someone else's";
}
