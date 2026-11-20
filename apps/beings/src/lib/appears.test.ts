import { describe, expect, it } from 'vitest';
import { groupAppearances } from './appears';

const link = (entity: string, name: string, kinds: string[], title: string) =>
  ({
    entity_id: entity,
    name,
    kinds,
    information_id: `${entity}-${title}`,
    title,
    type: 'note',
  }) as never;

describe('groupAppearances', () => {
  it('puts Sessions, Scenes and other entries in their own groups, by name', () => {
    const found = groupAppearances([
      link('a', 'Zeta', ['fact'], 'Oath'),
      link('b', 'The Siege', ['scene'], 'Text'),
      link('c', 'Session 3', ['session'], 'Recap'),
      link('d', 'Alpha', ['being'], 'Notes'),
    ]);

    expect(found.sessions.map((row) => row.name)).toEqual(['Session 3']);
    expect(found.scenes.map((row) => row.name)).toEqual(['The Siege']);
    expect(found.others.map((row) => row.name)).toEqual(['Alpha', 'Zeta']);
  });

  it('lists an entry once, with each title that links here', () => {
    const found = groupAppearances([
      link('a', 'Alpha', ['being'], 'Notes'),
      link('a', 'Alpha', ['being'], 'Backstory'),
      link('a', 'Alpha', ['being'], 'Notes'),
    ]);

    expect(found.others).toHaveLength(1);
    expect(found.others[0]?.titles).toEqual(['Notes', 'Backstory']);
  });

  it('is empty when nothing links here', () => {
    expect(groupAppearances([])).toEqual({ sessions: [], scenes: [], others: [] });
  });
});
