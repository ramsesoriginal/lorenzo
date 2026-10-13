import { describe, expect, it } from 'vitest';
import { type Explanation, explain } from './explain';

const names = new Map([
  ['dex', 'dexterity'],
  ['armour', 'armour_base'],
]);

const base = {
  stat_definition_id: 'x',
  name: 'armour_class',
  value: 15,
  own: false,
  computed: true,
  from_entity: null,
  contents: null,
};

describe('explain', () => {
  it('says a stored value is just that', () => {
    const out = explain({ ...base, computed: false, formula: null, inputs: [] }, names);

    expect(out.text).toBe('A value set on this being.');
    expect(out.parts).toEqual([]);
  });

  it('says a linear formula with its parts, offset and rounding', () => {
    const out = explain(
      {
        ...base,
        formula: {
          kind: 'linear',
          source_stat_definition_id: 'dex',
          multiplier: '0.5',
          offset: '10',
          round_mode: 'floor',
        },
        inputs: [{ stat_definition_id: 'dex', name: 'dexterity', value: 14 }],
      } as Explanation,
      names,
    );

    expect(out.text).toBe('Dexterity × 0.5 + 10, rounded down');
    expect(out.parts).toEqual([{ label: 'Dexterity', value: '14' }]);
  });

  it('says a sum by its terms', () => {
    const out = explain(
      {
        ...base,
        formula: {
          kind: 'sum',
          terms: [
            { stat_definition_id: 'armour', coefficient: '1' },
            { stat_definition_id: 'dex', coefficient: '2' },
          ],
          offset: '-1',
          round_mode: 'none',
        },
        inputs: [],
      } as Explanation,
      names,
    );

    expect(out.text).toBe('Armour base + 2 × Dexterity − 1');
  });

  it('says what a contents formula counted', () => {
    const out = explain(
      {
        ...base,
        formula: { kind: 'contents', source_stat_definition_id: 'dex' },
        inputs: [],
        contents: { source_stat_definition_id: 'dex', source_name: 'dexterity', things: 4 },
      } as Explanation,
      names,
    );

    expect(out.parts).toEqual([{ label: 'Things inside', value: '4' }]);
  });
});
