// The board's columns (ADR 0130, 0131): a being's or a group's, in the order
// controlled-by gives them - Equipped for a being and Not carried first and
// always, then every container it controls, then read-only columns for
// whatever else holds something of theirs - or, on the board of unowned
// things, one column per container as before (ADR 0077). Pure, so the order
// and the wording are tested without a page.
import type {
  ControlledByResponse,
  ControlledColumn,
  EntitySummary,
  ItemInstance,
  OwnedByResponse,
} from './types';

export interface BoardColumn {
  /** Unique on the board: the container's id, or 'loose' for things in none. */
  key: string;
  /** Whether a card can be dropped here: a read-only column takes none. */
  droppable: boolean;
  /** Where a card dropped here goes; null takes it out of every container. */
  dropTarget: string | null;
  title: string;
  /** Where the column's container is, when that's worth saying. */
  note: string | null;
  /** Whether the board's being carries it, which tints its note. */
  carried: boolean;
  /** Equipped and Not carried, the two places every board has (RFC 0031 §8). */
  fixed: boolean;
  /** What the column says when nothing's in it. */
  empty: string;
  /** Its container holds something the column doesn't list (ADR 0130). */
  contentsHidden: boolean;
  items: ItemInstance[];
}

const EMPTY_CONTAINER = 'This container is empty.';
const NOTHING_HERE = 'Nothing here.';

export interface Board {
  columns: BoardColumn[];
  /** Owner names by id, to mark what isn't the board's being's own. */
  owners: Map<string, string>;
  /** Whose board this is: a being, a group; null on the board of unowned things. */
  holderId: string | null;
  /** Whether the holder is a being, who carries what's in its own column. */
  holderIsBeing: boolean;
}

/** "in Carriage, in Stable": a container's surroundings, nearest first. */
function within(path: EntitySummary[]): string {
  return path.map((p) => `in ${p.name}`).join(', ');
}

function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Where a container column's container is: "In Backpack", "Brisk has these". */
function note(column: ControlledColumn, container: EntitySummary): string | null {
  const { path } = column;
  if (column.container_kind === 'being') {
    return `${container.name} has these${path.length > 0 ? `, ${within(path)}` : ''}`;
  }
  if (path.length > 0) return capitalized(within(path));
  // In nothing, and nobody carries it.
  return column.container_kind === 'item_instance' && !column.carried ? 'Not carried' : null;
}

function column(from: ControlledColumn): BoardColumn {
  const shared = { contentsHidden: from.contents_hidden, items: from.item_instances };
  if (from.kind === 'not_carried' || from.container === null) {
    // Dropping here takes a card out of every container: sets it down.
    return {
      ...shared,
      key: 'loose',
      droppable: true,
      dropTarget: null,
      title: 'Not carried',
      note: null,
      carried: false,
      fixed: true,
      empty: NOTHING_HERE,
    };
  }
  const container = from.container;
  if (from.kind === 'equipped') {
    // Dropping on Equipped puts a card into the being, who carries it (ADR 0115).
    return {
      ...shared,
      key: container.id,
      droppable: true,
      dropTarget: container.id,
      title: 'Equipped',
      note: null,
      carried: true,
      fixed: true,
      empty: 'Nothing equipped.',
    };
  }
  const readOnly = from.kind === 'read_only';
  return {
    ...shared,
    key: container.id,
    droppable: !readOnly,
    dropTarget: readOnly ? null : container.id,
    title: container.name,
    note: note(from, container),
    carried: from.carried,
    fixed: false,
    empty: EMPTY_CONTAINER,
  };
}

/** A being's or a group's board, from what it controls. */
export function controlledBoard(response: ControlledByResponse, holderId: string): Board {
  return {
    columns: response.columns.map(column),
    owners: new Map(response.owners.map((o) => [o.id, o.name])),
    holderId,
    holderIsBeing: response.columns.some((c) => c.kind === 'equipped'),
  };
}

/** The board of unowned things: what's in no container reads first. */
export function unownedBoard(response: OwnedByResponse): Board {
  const ordered = [...response.groups].sort((a, b) =>
    a.container === null ? -1 : b.container === null ? 1 : 0,
  );
  return {
    columns: ordered.map((g) => ({
      key: g.container?.id ?? 'loose',
      droppable: true,
      dropTarget: g.container?.id ?? null,
      title: g.container?.name ?? 'Unowned',
      note: null,
      carried: false,
      fixed: false,
      empty: g.container ? EMPTY_CONTAINER : NOTHING_HERE,
      contentsHidden: false,
      items: g.item_instances,
    })),
    owners: new Map(),
    holderId: null,
    holderIsBeing: false,
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
