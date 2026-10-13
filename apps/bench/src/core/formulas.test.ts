import { describe, expect, it } from 'vitest';
import {
  type Formula,
  fromBody,
  isDecimal,
  problems,
  same,
  describe as say,
  starting,
  toBody,
} from './formulas';
import type { StatDef } from './transport';

const defs: StatDef[] = [
  { id: 'w', name: 'Weight', type: 'float', enumValues: [] },
  { id: 'cw', name: 'Contents weight', type: 'float', enumValues: [] },
  { id: 'tw', name: 'Total weight', type: 'float', enumValues: [] },
  { id: 'm', name: 'Magical', type: 'bool', enumValues: [] },
  { id: 'load', name: 'Load', type: 'enum', enumValues: ['Light', 'Heavy'] },
];
const name = (id: string) => defs.find((d) => d.id === id)?.name ?? id;

describe('numbers', () => {
  it('reads a decimal with a point or a comma, and nothing else', () => {
    expect(isDecimal('2')).toBe(true);
    expect(isDecimal(' -0,5 ')).toBe(true);
    for (const t of ['', 'x', '1e3', '1.', '.5']) expect(isDecimal(t)).toBe(false);
  });
});

describe('starting formulas', () => {
  it('reads the first number stats that are not the stat itself', () => {
    expect(starting('sum', defs, 'w')).toEqual({
      kind: 'sum',
      terms: [{ stat: 'cw', coefficient: '1' }],
      offset: '0',
      round: 'none',
    });
    expect(starting('contents', defs, 'tw')).toEqual({ kind: 'contents', source: 'w' });
  });
});

describe('describing a formula', () => {
  it('says a sum as the design does', () => {
    const f: Formula = {
      kind: 'sum',
      terms: [
        { stat: 'w', coefficient: '2' },
        { stat: 'cw', coefficient: '1' },
      ],
      offset: '0',
      round: 'none',
    };
    expect(say(f, name)).toBe('2 × Weight + 1 × Contents weight');
    expect(say({ ...f, offset: '-3', round: 'floor' }, name)).toBe(
      '2 × Weight + 1 × Contents weight − 3, rounded (floor)',
    );
  });

  it('says the other kinds', () => {
    expect(
      say({ kind: 'linear', source: 'w', multiplier: '0,5', offset: '-5', round: 'floor' }, name),
    ).toBe('Weight × 0.5 − 5, rounded (floor)');
    expect(say({ kind: 'contents', source: 'w' }, name)).toBe(
      'Weight of everything inside, by how many',
    );
    expect(
      say(
        {
          kind: 'comparison',
          left: 'tw',
          comparator: 'gt',
          right: { constant: '10' },
          trueValue: 'Heavy',
          falseValue: 'Light',
        },
        name,
      ),
    ).toBe('Total weight is more than 10');
  });
});

describe('what cannot be saved', () => {
  it('needs a stat that is there, not the stat itself, once each, and numbers', () => {
    const bad: Formula = {
      kind: 'sum',
      terms: [
        { stat: 'tw', coefficient: 'x' },
        { stat: 'tw', coefficient: '1' },
        { stat: '', coefficient: '1' },
      ],
      offset: 'y',
      round: 'none',
    };
    expect(problems(bad, defs, 'tw')).toEqual(
      expect.arrayContaining([
        'A stat cannot be worked out from itself.',
        'The number in row 1 must be a number.',
        'Each stat can be added once.',
        'Choose the stat in row 3.',
        'The number added must be a number.',
      ]),
    );
  });

  it('is fine when it is complete', () => {
    expect(problems(starting('sum', defs, 'tw'), defs, 'tw')).toEqual([]);
  });

  it('wants both outcomes of a comparison for a stat that is not a tag', () => {
    const f = starting('comparison', defs, 'load');
    expect(problems(f, defs, 'load')).toContain(
      'Say what it is when the comparison holds, and when it does not.',
    );
    expect(problems(f, defs, 'm')).toEqual([]);
  });
});

describe('the API’s shape', () => {
  it('writes each kind, numbers as text with a point', () => {
    expect(
      toBody({ kind: 'linear', source: 'w', multiplier: '0,5', offset: '-5', round: 'floor' }),
    ).toEqual({
      kind: 'linear',
      source_stat_definition_id: 'w',
      multiplier: '0.5',
      offset: '-5',
      round_mode: 'floor',
    });
    expect(toBody({ kind: 'contents', source: 'w' })).toEqual({
      kind: 'contents',
      source_stat_definition_id: 'w',
    });
  });

  it('reads back what it writes', () => {
    const forms: Formula[] = [
      { kind: 'sum', terms: [{ stat: 'w', coefficient: '2' }], offset: '1', round: 'ceil' },
      { kind: 'linear', source: 'w', multiplier: '0.5', offset: '-5', round: 'floor' },
      { kind: 'contents', source: 'w' },
      {
        kind: 'comparison',
        left: 'w',
        comparator: 'ge',
        right: { constant: '3' },
        trueValue: 'a',
        falseValue: 'b',
      },
      {
        kind: 'comparison',
        left: 'w',
        comparator: 'lt',
        right: { stat: 'cw' },
        trueValue: '',
        falseValue: '',
      },
    ];
    for (const f of forms) expect(fromBody(toBody(f))).toEqual(f);
  });

  it('reads numbers the API sends as numbers', () => {
    expect(
      fromBody({
        kind: 'linear',
        source_stat_definition_id: 'w',
        multiplier: 0.5,
        offset: -5,
        round_mode: 'floor',
      }),
    ).toEqual({ kind: 'linear', source: 'w', multiplier: '0.5', offset: '-5', round: 'floor' });
  });

  it('is the same formula whatever the spelling of a number', () => {
    const a: Formula = {
      kind: 'linear',
      source: 'w',
      multiplier: '0.50',
      offset: '0',
      round: 'none',
    };
    const b: Formula = {
      kind: 'linear',
      source: 'w',
      multiplier: '0,5',
      offset: '0.0',
      round: 'none',
    };
    expect(same(a, b)).toBe(true);
    expect(same(a, { ...b, source: 'cw' })).toBe(false);
  });
});
