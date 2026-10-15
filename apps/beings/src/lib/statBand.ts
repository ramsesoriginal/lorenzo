// What the stat area of a being's sheet draws (RFC 0043): its stats grouped by the library's stat
// groups in the library's order, the numbers as tiles and the rest as rows, and the tags as chips.
// Where a value comes from is in each tile; the hints a definition carries (ADR 0279) say what to
// show beside it ("of 9", "+3") and where a stepper should stop.

import type { StatDefinition, VocabularyEntry } from '@lorenzo/stat-values';
import { statLabel } from './statLabel';
import type { EntityDetail } from './types';

type StatValue = EntityDetail['stats'][number];

export type Tile = {
  /** The definition's id, to write the stat by. */
  id: string;
  name: string;
  label: string;
  /** Null for an unset stat in the selected being group. */
  value: number | string | null;
  numeric: boolean;
  valueType: StatDefinition['value_type'];
  unit: string | null;
  /** Drawn with a sign ("+3"). */
  signed: boolean;
  /** The library lets a player change it while playing. */
  adjustable: boolean;
  /** The library keeps it in view in the sticky bar. */
  pinned: boolean;
  // The being holds the value itself, rather than getting it from a prototype or a formula.
  own: boolean;
  // A formula produced the value.
  computed: boolean;
  // Where an inherited or calculated value comes from, by name.
  from: string | null;
  /** The maximum hint's value on this being, for "of 9". */
  of: number | string | null;
  /** The resolved hint's value on this being, as the text to show beside it ("+3"). */
  resolved: string | null;
  /** The minimum hint's value on this being: a stepper does not go below it. */
  floor: number | null;
};

export type BandGroup = { name: string; tiles: Tile[]; rows: Tile[] };

export type Tag = {
  id: string;
  name: string;
  label: string;
  state: 'on' | 'off' | 'inherited';
  /** What the tag is on or off from, when inherited. */
  from: string | null;
  adjustable: boolean;
};

const NUMBER_TYPES = new Set(['int', 'float']);

/** A number with its sign, the minus a real one: "+3", "−1", "±0". */
export function signed(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '±';

  return `${sign}${Math.abs(value)}`;
}

/** A tile's value as text, with its sign when the library says so; the unit is drawn apart. */
export function shownValue(tile: Pick<Tile, 'value' | 'numeric' | 'signed'>): string {
  if (tile.value === null) return '—';

  return tile.signed && tile.numeric && typeof tile.value === 'number'
    ? signed(tile.value)
    : String(tile.value);
}

/** What goes beside a number: "of 9", the resolved stat's value, or both. */
export function captionOf(tile: Pick<Tile, 'of' | 'resolved'>): string {
  return [tile.resolved, tile.of !== null ? `of ${tile.of}` : null].filter(Boolean).join(' · ');
}

const hasValue = (stat: StatValue | undefined): stat is StatValue => stat !== undefined;

/** A stat's value if it is a number or text; a tag has no number to show beside a tile. */
const plainValue = (stat: StatValue | undefined): number | string | null =>
  stat === undefined || typeof stat.value === 'boolean' ? null : stat.value;

/** The groups of tiles for a being, in the library's order; stats of no known group come last. */
export function bandOf(
  vocabulary: readonly VocabularyEntry[],
  entity: Pick<EntityDetail, 'stats'>,
  options: { beingStatGroupId?: string | null } = {},
): BandGroup[] {
  const byName = new Map(vocabulary.map((entry) => [entry.definition.name, entry]));
  const byId = new Map(vocabulary.map((entry) => [entry.definition.id, entry]));
  const stats = new Map(entity.stats.map((stat) => [stat.name, stat]));
  const groups = new Map<string, BandGroup>();

  for (const entry of vocabulary) {
    if (entry.definition.value_type !== 'bool') {
      groups.set(entry.group, { name: entry.group, tiles: [], rows: [] });
    }
  }

  const statNamed = (id: string | null): StatValue | undefined => {
    const entry = id ? byId.get(id) : undefined;

    return entry ? stats.get(entry.definition.name) : undefined;
  };

  const resolvedText = (id: string | null): string | null => {
    const stat = statNamed(id);
    const entry = id ? byId.get(id) : undefined;

    if (!hasValue(stat) || typeof stat.value === 'boolean') return null;
    if (entry?.definition.signed && typeof stat.value === 'number') return signed(stat.value);

    return String(stat.value);
  };

  const numberOf = (id: string | null): number | null => {
    const stat = statNamed(id);

    return hasValue(stat) && typeof stat.value === 'number' ? stat.value : null;
  };

  const tileOf = (
    name: string,
    value: number | string | null,
    stat: StatValue | undefined,
  ): { group: string; tile: Tile } => {
    const entry = byName.get(name);
    const definition = entry?.definition;
    const numeric = definition ? NUMBER_TYPES.has(definition.value_type) : false;

    return {
      group: entry?.group ?? '',
      tile: {
        id: definition?.id ?? '',
        name,
        label: statLabel(name),
        value,
        numeric,
        valueType: definition?.value_type ?? 'text',
        unit: definition?.unit ?? null,
        signed: definition?.signed ?? false,
        adjustable: definition?.adjustable_in_play ?? false,
        pinned: definition?.pin ?? false,
        own: stat?.own ?? false,
        computed: stat?.computed === true,
        from: stat?.from_entity?.name ?? null,
        of: plainValue(statNamed(definition?.max_hint_id ?? null)),
        resolved: resolvedText(definition?.resolved_hint_id ?? null),
        floor: numberOf(definition?.min_hint_id ?? null),
      },
    };
  };
  const place = ({ group: groupName, tile }: { group: string; tile: Tile }) => {
    const group = groups.get(groupName) ?? { name: groupName, tiles: [], rows: [] };

    (tile.numeric ? group.tiles : group.rows).push(tile);
    groups.set(groupName, group);
  };

  // Every stat the being has.
  for (const stat of entity.stats) {
    if (typeof stat.value !== 'boolean') place(tileOf(stat.name, stat.value, stat));
  }

  // The primary being group stays present even before its values are filled (ADR 0297).
  if (options.beingStatGroupId) {
    for (const entry of vocabulary) {
      if (
        entry.groupId === options.beingStatGroupId &&
        entry.definition.value_type !== 'bool' &&
        !stats.has(entry.definition.name)
      ) {
        place(tileOf(entry.definition.name, null, undefined));
      }
    }
  }

  // Within a group, the library's order: the entity lists stats in it already, but a tile of a
  // definition the viewer cannot see keeps its place at the end.
  const position = new Map(vocabulary.map((entry, index) => [entry.definition.name, index]));
  const byLibrary = (a: Tile, b: Tile) =>
    (position.get(a.name) ?? Number.MAX_SAFE_INTEGER) -
    (position.get(b.name) ?? Number.MAX_SAFE_INTEGER);

  return [...groups.values()]
    .filter((group) => group.tiles.length + group.rows.length > 0)
    .map((group) => ({
      ...group,
      tiles: [...group.tiles].sort(byLibrary),
      rows: [...group.rows].sort(byLibrary),
    }));
}

/**
 * The numbers kept in the sticky bar: the ones the library pins, in its order; with none pinned,
 * the first few number tiles of the first group that has any.
 */
export function vitalsOf(groups: readonly BandGroup[], count = 3): Tile[] {
  const pinned = groups
    .flatMap((group) => group.tiles)
    .filter((tile) => tile.pinned && tile.value !== null);

  if (pinned.length > 0) return pinned;

  return groups.find((group) => group.tiles.length > 0)?.tiles.slice(0, count) ?? [];
}

/** A tile's value as text with its unit: "30 ft". */
export const valueText = (tile: Pick<Tile, 'value' | 'unit' | 'numeric' | 'signed'>): string =>
  tile.unit ? `${shownValue(tile)} ${tile.unit}` : shownValue(tile);

/**
 * The library's tags (bool stats of its `tags` group) and what each is on this being: on, off, or
 * what it inherits.
 */
export function tagsOf(
  vocabulary: readonly VocabularyEntry[],
  entity: Pick<EntityDetail, 'stats'>,
): Tag[] {
  const stats = new Map(entity.stats.map((stat) => [stat.name, stat]));

  return vocabulary
    .filter((entry) => entry.definition.value_type === 'bool' && entry.group === 'tags')
    .map(({ definition }) => {
      const stat = stats.get(definition.name);
      const on = stat?.value === true;
      const state: Tag['state'] = stat?.own ? (on ? 'on' : 'off') : 'inherited';

      return {
        id: definition.id,
        name: definition.name,
        label: statLabel(definition.name),
        state,
        from: stat && !stat.own ? (stat.from_entity?.name ?? null) : null,
        adjustable: definition.adjustable_in_play,
      };
    });
}

/** Whether a tag is in force on the being: set on, or inherited as on. */
export function tagIsOn(tag: Tag, entity: Pick<EntityDetail, 'stats'>): boolean {
  return entity.stats.some((stat) => stat.name === tag.name && stat.value === true);
}
