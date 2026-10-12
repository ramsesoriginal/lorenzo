// What the stat area of a being's sheet draws (RFC 0043): its stats grouped by the library's stat
// groups, the numbers as tiles and the rest as rows. Only stats the being has a value for; the tags
// (bool stats) are the header's. Where a value comes from is in each tile.

import type { StatDefinition } from '@lorenzo/stat-values';
import { statLabel } from './statLabel';
import type { EntityDetail } from './types';

export type Tile = {
  name: string;
  label: string;
  value: number | string;
  numeric: boolean;
  unit: string | null;
  // The being holds the value itself, rather than getting it from a prototype or a formula.
  own: boolean;
  // A formula produced the value.
  computed: boolean;
  // Where an inherited or calculated value comes from, by name.
  from: string | null;
};

export type BandGroup = { name: string; tiles: Tile[]; rows: Tile[] };

type Defined = { definition: StatDefinition; group: string };

const NUMBER_TYPES = new Set(['int', 'float']);

/** The groups of tiles for a being, in the library's order; stats of no known group come last. */
export function bandOf(definitions: readonly Defined[], entity: Pick<EntityDetail, 'stats'>) {
  const byName = new Map(definitions.map((entry) => [entry.definition.name, entry]));
  const groups = new Map<string, BandGroup>();

  for (const entry of definitions) {
    groups.set(entry.group, { name: entry.group, tiles: [], rows: [] });
  }

  for (const stat of entity.stats) {
    if (typeof stat.value === 'boolean') continue;

    const entry = byName.get(stat.name);
    const groupName = entry?.group ?? '';
    const group = groups.get(groupName) ?? { name: groupName, tiles: [], rows: [] };
    const numeric = entry ? NUMBER_TYPES.has(entry.definition.value_type) : false;
    const tile: Tile = {
      name: stat.name,
      label: statLabel(stat.name),
      value: stat.value,
      numeric,
      unit: entry?.definition.unit ?? null,
      own: stat.own,
      computed: stat.computed === true,
      from: stat.from_entity?.name ?? null,
    };

    (numeric ? group.tiles : group.rows).push(tile);
    groups.set(groupName, group);
  }

  return [...groups.values()].filter((group) => group.tiles.length + group.rows.length > 0);
}

/** The numbers kept in the sticky bar: the first few number tiles of the first group that has any. */
export function vitalsOf(groups: readonly BandGroup[], count = 3): Tile[] {
  return groups.find((group) => group.tiles.length > 0)?.tiles.slice(0, count) ?? [];
}

/** A tile's value as text: its unit follows it. */
export const valueText = (tile: Pick<Tile, 'value' | 'unit'>): string =>
  tile.unit ? `${tile.value} ${tile.unit}` : String(tile.value);
