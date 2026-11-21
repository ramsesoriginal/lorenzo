// The three ways to see the list of beings (BN1, BN4 of docs/design/web/beings): rows, cards, and
// side by side. The choice is the person's and is kept in this browser. Cards and side by side
// show numbers, which take a read of each being; that is `numbersOf`, with its own pace.

import type { VocabularyEntry } from '@lorenzo/stat-values';
import { bandOf, type Tile, valueText, vitalsOf } from './statBand';
import { statLabel } from './statLabel';
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
  /** The definition's id and name, and what readers call it. */
  id: string;
  name: string;
  label: string;
  /** "14 / 20", "+3", "—". */
  text: string;
  /** The value alone, as the card and the band draw it big: "14", "+3". */
  shown: string;
  derived: boolean;
  /** The number itself, and what Play needs to change it. */
  value: number | null;
  own: boolean;
  floor: number | null;
  of: number | string | null;
  adjustable: boolean;
};

/** A being's numbers in the library's order, and the few the library pins (or the first ones). */
export type Numbers = { all: Number[]; vitals: Number[] };

const numberOf = (tile: Tile): Number => ({
  id: tile.id,
  name: tile.name,
  label: tile.label,
  text: tile.of === null ? valueText(tile) : `${valueText(tile)} / ${tile.of}`,
  shown: valueText(tile),
  derived: tile.computed,
  value: typeof tile.value === 'number' ? tile.value : null,
  own: tile.own,
  floor: tile.floor,
  of: tile.of,
  adjustable: tile.adjustable && !tile.computed && Boolean(tile.id),
});

/** The stats other stats name as their limit or resolved value: they show beside a number, not as one. */
export function hintIdsOf(vocabulary: readonly VocabularyEntry[]): Set<string> {
  const ids = new Set<string>();

  for (const { definition } of vocabulary) {
    for (const id of [
      definition.max_hint_id,
      definition.min_hint_id,
      definition.resolved_hint_id,
    ]) {
      if (id) ids.add(id);
    }
  }

  return ids;
}

/** The numbers a being has: only tiles that hold a number, not tags or lines of text. */
export function numbersOf(
  vocabulary: readonly VocabularyEntry[],
  entity: Pick<EntityDetail, 'stats'>,
): Numbers {
  const hints = hintIdsOf(vocabulary);
  const groups = bandOf(vocabulary, entity).map((group) => ({
    ...group,
    tiles: group.tiles.filter((tile) => tile.numeric && !hints.has(tile.id)),
  }));

  return {
    all: groups.flatMap((group) => group.tiles).map(numberOf),
    vitals: vitalsOf(groups).map(numberOf),
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

/**
 * The numbers the rows of the list show beside the name (BN1): the library's pinned numbers first,
 * then its other numbers, two in all. Taken from the library's vocabulary, so every row has the same columns.
 */
export function columnsOf(
  vocabulary: readonly VocabularyEntry[],
  count = 2,
): { name: string; label: string }[] {
  const hints = hintIdsOf(vocabulary);
  const numeric = vocabulary.filter(
    ({ definition }) =>
      (definition.value_type === 'int' || definition.value_type === 'float') &&
      !hints.has(definition.id),
  );
  const pinned = numeric.filter(({ definition }) => definition.pin);
  const rest = numeric.filter(({ definition }) => !definition.pin);

  return [...pinned, ...rest].slice(0, count).map(({ definition }) => ({
    name: definition.name,
    label: statLabel(definition.name),
  }));
}
