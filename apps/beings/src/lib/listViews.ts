// The three ways to see the list of beings (BN1, BN4 of docs/design/web/beings): rows, cards, and
// side by side. The choice is the person's and is kept in this browser. Cards and side by side
// show numbers, which take a read of each being; that is `numbersOf`, with its own pace.

import type { VocabularyEntry } from '@lorenzo/stat-values';
import { bandOf, type Tile, valueText, vitalsOf } from './statBand';
import type { EntityDetail } from './types';

export type ListView = 'rows' | 'cards' | 'side';

export const LIST_VIEWS: readonly { view: ListView; label: string }[] = [
  { view: 'rows', label: 'Rows' },
  { view: 'cards', label: 'Cards' },
  { view: 'side', label: 'Side by side' },
];

export const LIST_VIEW_KEY = 'lorenzo:beings:view';

export const isListView = (value: string | null | undefined): value is ListView =>
  value === 'rows' || value === 'cards' || value === 'side';

// localStorage can throw (private browsing, disabled): then nothing is remembered.
export function savedView(): ListView {
  try {
    const saved = window.localStorage.getItem(LIST_VIEW_KEY);

    return isListView(saved) ? saved : 'rows';
  } catch {
    return 'rows';
  }
}

export function rememberView(view: ListView): void {
  try {
    window.localStorage.setItem(LIST_VIEW_KEY, view);
  } catch {
    // Nothing is remembered, and the list opens as rows next time.
  }
}

/** One number of a being, as the list shows it. */
export type Number = {
  name: string;
  label: string;
  /** "14 / 20", "+3", "—". */
  text: string;
  derived: boolean;
};

/** A being's numbers in the library's order, and the few the library pins (or the first ones). */
export type Numbers = { all: Number[]; vitals: Number[] };

const numberOf = (tile: Tile): Number => ({
  name: tile.name,
  label: tile.label,
  text: tile.of === null ? valueText(tile) : `${valueText(tile)} / ${tile.of}`,
  derived: tile.computed,
});

/** The numbers a being has: only tiles that hold a number, not tags or lines of text. */
export function numbersOf(
  vocabulary: readonly VocabularyEntry[],
  entity: Pick<EntityDetail, 'stats'>,
): Numbers {
  const groups = bandOf(vocabulary, entity);
  const all = groups.flatMap((group) => group.tiles).filter((tile) => tile.numeric);

  return {
    all: all.map(numberOf),
    vitals: vitalsOf(
      groups.map((group) => ({ ...group, tiles: group.tiles.filter((t) => t.numeric) })),
    ).map(numberOf),
  };
}

/** What a vital says on a card: "14 / 20 hit points". */
export const vitalLine = (number: Number): string => `${number.text} ${number.label.toLowerCase()}`;

/**
 * The rows of the side-by-side table: every number any of the beings has, once, in the order they
 * first appear (the library's order, as each being's numbers already are).
 */
export function sideRows(
  numbers: readonly (Numbers | undefined)[],
): { name: string; label: string; derived: boolean }[] {
  const rows = new Map<string, { name: string; label: string; derived: boolean }>();

  for (const being of numbers) {
    for (const number of being?.all ?? []) {
      if (!rows.has(number.name)) {
        rows.set(number.name, { name: number.name, label: number.label, derived: number.derived });
      }
    }
  }

  return [...rows.values()];
}

/** Runs `work` over `items`, at most `limit` at once, keeping each result at its item's place. */
export async function mapLimited<T, R>(
  items: readonly T[],
  limit: number,
  work: (item: T) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;

  async function worker() {
    while (next < items.length) {
      const at = next++;

      results[at] = await work(items[at] as T);
    }
  }

  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}
