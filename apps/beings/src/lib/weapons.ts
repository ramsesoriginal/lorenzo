// The datasheet's weapons as a table (ADR 0281): pure, so it is tested without a network.

import type { VocabularyEntry } from '@lorenzo/stat-values';
import type { SheetWeapon } from './sheet';
import { shownValue } from './statBand';
import { statLabel } from './statLabel';

export type WeaponTable = {
  columns: { name: string; label: string }[];
  rows: { id: string; name: string; quantity: number | null; cells: string[] }[];
};

/**
 * The weapons as a table: a column for each stat any of them has, in the library's order, and "—" where one has no value. Units and signs are the library's.
 */
export function weaponTable(
  weapons: readonly SheetWeapon[],
  vocabulary: readonly VocabularyEntry[],
) {
  const byName = new Map(vocabulary.map((entry) => [entry.definition.name, entry.definition]));
  const position = new Map(vocabulary.map((entry, index) => [entry.definition.name, index]));
  // The library's order, so a weapon that lacks the first stat does not put it last.
  const names = [
    ...new Set(weapons.flatMap((weapon) => weapon.stats.map((stat) => stat.name))),
  ].sort(
    (a, b) =>
      (position.get(a) ?? Number.MAX_SAFE_INTEGER) - (position.get(b) ?? Number.MAX_SAFE_INTEGER),
  );
  const numeric = (name: string) => {
    const type = byName.get(name)?.value_type;

    return type === 'int' || type === 'float';
  };

  return {
    columns: names.map((name) => ({ name, label: statLabel(name) })),
    rows: weapons.map((weapon) => ({
      id: weapon.entity_id,
      name: weapon.name,
      quantity: weapon.quantity,
      cells: names.map((name) => {
        const stat = weapon.stats.find((candidate) => candidate.name === name);

        if (!stat || typeof stat.value === 'boolean') return '—';

        const definition = byName.get(name);
        const text = shownValue({
          value: stat.value,
          numeric: numeric(name),
          signed: definition?.signed ?? false,
        });

        return definition?.unit ? `${text} ${definition.unit}` : text;
      }),
    })),
  } satisfies WeaponTable;
}

/** What to say where a section of the datasheet has nothing: a missing setting is a different thing. */
export function emptySection(configured: boolean, what: string): string {
  return configured
    ? `Nothing to show: no ${what}.`
    : `The library has not said where to find ${what} yet.`;
}
