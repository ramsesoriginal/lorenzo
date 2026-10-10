import { describe, expect, it } from 'vitest';
import { normalize, score, suggest } from './fuzzy';

describe('normalize', () => {
  it('drops case, accents, punctuation and extra space', () => {
    expect(normalize('  Éclair,  Hooded! ')).toBe('eclair hooded');
  });
});

describe('score', () => {
  it('is 1 for the same name however it is written', () => {
    expect(score('Torch', 'torch.')).toBe(1);
  });

  it('is 0 for nothing, and for an empty name', () => {
    expect(score('', 'Torch')).toBe(0);
    expect(score('Torch', 'Anvil')).toBeLessThan(0.2);
  });

  it('finds a plural and a word inside a longer title', () => {
    expect(score('Torches', 'Torch')).toBeGreaterThan(0.6);
    expect(score('Torch', 'Torch, Hooded')).toBeGreaterThan(0.7);
  });

  it('finds the same words in another order', () => {
    expect(score('healing potion', 'Potion of Healing')).toBeGreaterThan(0.4);
  });
});

describe('suggest', () => {
  const catalog = ['Anvil', 'Torch', 'Potion of Healing', 'Torch, Hooded', 'Rope'];

  it('gives the best first, up to the count', () => {
    expect(suggest('torches', catalog, (t) => t, 2)).toEqual(['Torch', 'Torch, Hooded']);
  });

  it('gives nothing when nothing is alike', () => {
    expect(suggest('zzzz', catalog, (t) => t, 3)).toEqual([]);
  });
});
