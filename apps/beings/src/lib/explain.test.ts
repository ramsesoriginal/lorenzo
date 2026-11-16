import { describe, expect, it } from 'vitest';
import { type Explanation, explain } from './explain';

const names = new Map([
  ['dex', 'dexterity'],
  ['armour', 'armour_base'],
]);

const base = {
  stat_definition_id: 'x',
  group_id: 'g',
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

  it('says a select by the step it took, or that none applied', () => {
    const select = {
      kind: 'select',
      source_stat_definition_id: 'dex',
      mode: 'threshold',
      steps: [
        { from: '1', result: { number: '2' } },
        { from: '5', result: { number: '3' } },
      ],
      otherwise: null,
    };
    const took = explain(
      {
        ...base,
        formula: select,
        inputs: [],
        chosen: { position: 1, otherwise: false, key: 5 },
      } as Explanation,
      names,
    );
    const fell = explain(
      {
        ...base,
        formula: select,
        inputs: [],
        chosen: { position: null, otherwise: true, key: null },
      } as Explanation,
      names,
    );

    expect(took.text).toBe('Dexterity looked up in a table of 2 steps');
    expect(took.parts).toEqual([{ label: 'Step taken', value: 'step 2 (5)' }]);
    expect(fell.parts).toEqual([{ label: 'Step taken', value: 'none matched, so the default' }]);
  });

  it('says a product by its factors and a ratio with its rounding', () => {
    const product = explain(
      {
        ...base,
        formula: {
          kind: 'product',
          factors: ['dex', 'armour'],
          multiplier: '2',
          offset: '1',
          round_mode: 'none',
        },
        inputs: [],
      } as Explanation,
      names,
    );
    const ratio = explain(
      {
        ...base,
        division_rounded: true,
        formula: {
          kind: 'ratio',
          numerator_stat_definition_id: 'dex',
          denominator_stat_definition_id: null,
          denominator_constant: '3',
          multiplier: '1',
          offset: '0',
          round_mode: 'floor',
        },
        inputs: [],
      } as Explanation,
      names,
    );

    expect(product.text).toBe('Dexterity × Armour base × 2 + 1');
    expect(ratio.text).toBe('Dexterity ÷ 3, rounded down, the division rounded to 28 digits');
  });

  it('says what a dice value reads of its dice, and how it is rounded', () => {
    const read = (as: string, round_mode: string) =>
      explain(
        {
          ...base,
          formula: { kind: 'dice_value', source_stat_definition_id: 'dex', as, round_mode },
          inputs: [],
        } as Explanation,
        names,
      ).text;

    expect(read('max', 'none')).toBe('The largest roll of Dexterity');
    expect(read('min', 'none')).toBe('The smallest roll of Dexterity');
    expect(read('average', 'floor')).toBe('The average roll of Dexterity, rounded down');
  });

  it('says dice built from a count and a number of sides', () => {
    const built = explain(
      {
        ...base,
        formula: {
          kind: 'dice',
          count_stat_definition_id: 'dex',
          count_constant: null,
          sides_stat_definition_id: null,
          sides_constant: 8,
        },
        inputs: [],
      } as Explanation,
      names,
    );

    expect(built.text).toBe('Dexterity dice of 8 sides');
  });

  it('says a contents formula by its aggregate and what it keeps', () => {
    const best = explain(
      {
        ...base,
        formula: {
          kind: 'contents',
          source_stat_definition_id: 'armour',
          aggregate: 'max',
          only_active: true,
        },
        inputs: [],
        contents: { source_stat_definition_id: 'armour', source_name: 'armour_base', things: 2 },
      } as Explanation,
      names,
    );
    const attuned = explain(
      {
        ...base,
        formula: {
          kind: 'contents',
          source_stat_definition_id: null,
          aggregate: 'count',
          only_active: false,
        },
        inputs: [],
        contents: { source_stat_definition_id: null, source_name: null, things: 3 },
      } as Explanation,
      names,
    );

    expect(best.text).toBe('The largest Armour base of what is inside that is switched on');
    expect(attuned.text).toBe('How many things inside');
    expect(attuned.parts).toEqual([{ label: 'Things inside', value: '3' }]);
  });

  it('says a cap and a floor by what they compare', () => {
    const cap = explain(
      {
        ...base,
        formula: {
          kind: 'min',
          inputs: [{ stat_definition_id: 'dex' }, { constant: '2' }],
          round_mode: 'none',
        },
        inputs: [{ stat_definition_id: 'dex', name: 'dexterity', value: 4 }],
      } as Explanation,
      names,
    );
    const floor = explain(
      {
        ...base,
        formula: {
          kind: 'max',
          inputs: [{ stat_definition_id: 'armour' }, { constant: '0' }],
          round_mode: 'floor',
        },
        inputs: [],
      } as Explanation,
      names,
    );

    expect(cap.text).toBe('The smaller of Dexterity, 2');
    expect(floor.text).toBe('The larger of Armour base, 0, rounded down');
  });

  it('says what a contents formula counted', () => {
    const out = explain(
      {
        ...base,
        formula: {
          kind: 'contents',
          source_stat_definition_id: 'dex',
          aggregate: 'sum',
          only_active: false,
        },
        inputs: [],
        contents: { source_stat_definition_id: 'dex', source_name: 'dexterity', things: 4 },
      } as Explanation,
      names,
    );

    expect(out.parts).toEqual([{ label: 'Things inside', value: '4' }]);
  });
});
