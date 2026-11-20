// Who plays each being, for the list (BN1): the players of the campaigns the viewer may list, by the
// character each plays. A being no roster names is "Not played"; where no roster could be read the
// list says nothing about it. Pure, so it is tested without a browser.

type Seat = {
  display_name?: string | null;
  nickname?: string | null;
  characters: { entity_id: string }[];
};

/** The characters each player has, as the players' names, owner or not. */
export function playedByOf(rosters: readonly (readonly Seat[])[]): Map<string, string[]> {
  const found = new Map<string, string[]>();

  for (const seat of rosters.flat()) {
    const name = seat.display_name || seat.nickname || 'A player';

    for (const character of seat.characters) {
      const names = found.get(character.entity_id) ?? [];

      if (!names.includes(name)) names.push(name);
      found.set(character.entity_id, names);
    }
  }

  return found;
}

/** What the "Played by" column says of a being. `known` is whether any roster was read at all. */
export function playedByText(
  names: readonly string[] | undefined,
  isCharacter: boolean,
  known: boolean,
): string {
  if (names && names.length > 0) return names.join(', ');
  if (!known) return '—';

  return isCharacter ? '—' : 'Not played';
}
