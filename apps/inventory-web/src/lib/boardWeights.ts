// What each column of a board weighs and how much room it has left (IN8, IN11 of
// docs/design/web/inventory-web): "12 of 12 lb · full", "3 of 4 lb · 1 lb free", "5 lb", and the weight
// the being carries against what it can. Pure, so the words are tested without a page. The API
// still refuses a move that would go over a limit (ADR 0128); this only says it beforehand.

import type { Board, BoardColumn } from './boardColumns';
import type { ItemInstance } from './types';

/** An item's weight with its quantity: a stack of six that weighs one each weighs six. Null if unknown. */
export function weightOf(item: Pick<ItemInstance, 'weight' | 'quantity'>): number | null {
  if (item.weight === null || item.weight === undefined) return null;

  return item.weight * (item.quantity ?? 1);
}

/** What the items add up to; the ones with no weight count as nothing. */
export function totalWeight(items: readonly Pick<ItemInstance, 'weight' | 'quantity'>[]): number {
  return items.reduce((sum, item) => sum + (weightOf(item) ?? 0), 0);
}

/** A number as people write it: "12", "2.5", never "2.50". */
export function shownNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
}

/** "12 lb", or "12" where the library names no unit. */
export function withUnit(value: number, unit: string | null): string {
  return unit ? `${shownNumber(value)} ${unit}` : shownNumber(value);
}

/**
 * What a column says about its weight: "5 lb" with no limit, "12 of 12 lb · full" at the limit and
 * "3 of 4 lb · 1 lb free" under it; over it (a GM moved it anyway, ADR 0128) "14 of 12 lb · 2 lb over".
 */
export function weightLine(used: number, limit: number | null, unit: string | null): string {
  if (limit === null) return withUnit(used, unit);

  const base = `${shownNumber(used)} of ${withUnit(limit, unit)}`;

  if (used === limit) return `${base} · full`;
  if (used > limit) return `${base} · ${withUnit(used - limit, unit)} over`;

  return `${base} · ${withUnit(limit - used, unit)} free`;
}

/**
 * The line under a column's name: its weight, then where it is. Equipped says who holds it and
 * Not carried that it is set down; a container says where it is ("Imani has these"); a read-only
 * column who has it ("Not carried, with Mara Quill").
 */
export function columnLine(
  column: Pick<BoardColumn, 'fixed' | 'dropTarget' | 'note' | 'title'>,
  weight: string,
  holderName: string | null,
): string {
  const where =
    column.fixed && column.dropTarget !== null
      ? holderName
        ? `${holderName} holds these`
        : null
      : column.fixed
        ? 'Set down'
        : column.note;

  return where ? `${weight} · ${where}` : weight;
}

/** What the being carries: what is in the columns it carries (Equipped, and its carried containers). */
export function carriedWeight(board: Pick<Board, 'columns'>): number {
  return board.columns
    .filter((column) => column.carried)
    .reduce((sum, column) => sum + totalWeight(column.items), 0);
}

/** What a drag says about the column under it (IN12): where it would land and why not, in words. */
export type DropVerdict = { kind: 'ok' | 'join' | 'refuse'; text: string };

/**
 * What a column says to a card being dragged to it. `there` is what the column holds now, `moved` what
 * is dragged, `limit` what the column can carry (null: no limit). A single item that is identical to a
 * stack already there joins it (ADR 0133). Over the limit it is refused, with the sum, as the API
 * would (ADR 0128).
 */
export function dropVerdict(input: {
  moved: readonly ItemInstance[];
  there: readonly ItemInstance[];
  limit: number | null;
  unit: string | null;
  columnName: string;
  /** Another stack of the same item, when one is there. */
  joins: ItemInstance | null;
}): DropVerdict {
  const after = totalWeight(input.there) + totalWeight(input.moved);

  if (input.limit !== null && after > input.limit) {
    return {
      kind: 'refuse',
      text: `Too heavy: the ${input.columnName.toLowerCase()} holds ${withUnit(input.limit, input.unit)}, this would make ${shownNumber(after)}`,
    };
  }

  const [only] = input.moved;

  if (input.joins && input.moved.length === 1 && only) {
    const together = (input.joins.quantity ?? 1) + (only.quantity ?? 1);

    return {
      kind: 'join',
      text: `Joins ${input.joins.title} × ${input.joins.quantity ?? 1}, making ${together}`,
    };
  }

  if (input.limit !== null) {
    return {
      kind: 'ok',
      text: `Makes ${shownNumber(after)} of ${withUnit(input.limit, input.unit)}`,
    };
  }

  return { kind: 'ok', text: after > 0 ? `Makes ${withUnit(after, input.unit)}` : 'Goes here' };
}
