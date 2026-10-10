import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { alternatives, builtinTable, parseTable } from '../src/index';

type Vector = { name: string; alternatives: string[] };

// The same list apps/cli runs against its Python reader (ADR 0242).
const vectors = JSON.parse(
  readFileSync(new URL('../vectors.json', import.meta.url), 'utf-8'),
) as Vector[];

describe('the built-in table', () => {
  it.each(vectors.map((v) => [v.name, v.alternatives] as const))(
    '%j gives %j',
    (name, expected) => {
      expect(alternatives(name, builtinTable())).toEqual(expected);
    },
  );
});

describe('parseTable', () => {
  const table = parseTable(`
[names]
"Kiste" = "Chest"
"Armbrustbolzen" = ["Crossbow bolts (20)", "Bolts (20)"]

[words]
"Seil" = "Rope"
`);

  it('reads a title or a list, without case', () => {
    expect(alternatives('kiste', table)).toEqual(['chest']);
    expect(alternatives('Armbrustbolzen', table)).toEqual(['crossbow bolts (20)', 'bolts (20)']);
  });

  it('translates a word inside a longer name', () => {
    expect(alternatives('Langes Seil', table)).toEqual(['langes rope']);
  });

  it('never gives the name back', () => {
    expect(alternatives('Chest', parseTable('[names]\n"chest" = "Chest"'))).toEqual([]);
  });
});

describe('hostile names', () => {
  // Names come from players: nothing here may take time that grows faster than the name does.
  it.each([
    ['spaces', ' '.repeat(50_000)],
    ['openers', '('.repeat(50_000)],
    ['dollars and spaces', '$ '.repeat(25_000)],
    ['digits', '1 '.repeat(25_000)],
  ])('answers a name of %s quickly', (_, name) => {
    const started = performance.now();

    alternatives(name, builtinTable());

    expect(performance.now() - started).toBeLessThan(1000);
  });
});
