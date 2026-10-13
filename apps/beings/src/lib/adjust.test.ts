import { describe, expect, it } from 'vitest';
import { nextValue, parseAmount, UndoStack } from './adjust';

describe('nextValue', () => {
  it('takes away, adds, sets and steps', () => {
    expect(nextValue(31, 'sub', 7, null)).toBe(24);
    expect(nextValue(24, 'add', 3, null)).toBe(27);
    expect(nextValue(24, 'set', 40, null)).toBe(40);
    expect(nextValue(5, 'step-down', 1, null)).toBe(4);
    expect(nextValue(5, 'step-up', 1, null)).toBe(6);
  });

  it('stops at the floor when the definition names one, and nowhere when it does not', () => {
    expect(nextValue(3, 'sub', 10, 0)).toBe(0);
    expect(nextValue(3, 'step-down', 1, 3)).toBe(3);
    expect(nextValue(3, 'sub', 10, null)).toBe(-7);
  });
});

describe('parseAmount', () => {
  it('accepts numbers of zero or more, with a point or a comma', () => {
    expect(parseAmount('7')).toBe(7);
    expect(parseAmount(' 2,5 ')).toBe(2.5);
    expect(parseAmount('0')).toBe(0);
  });

  it('refuses everything else', () => {
    for (const text of ['', ' ', '-1', 'x', '1e3', '1.']) expect(parseAmount(text)).toBeNull();
  });
});

describe('UndoStack', () => {
  it('gives the changes back newest first, and forgets the oldest past its limit', async () => {
    const stack = new UndoStack(2);
    const seen: string[] = [];

    for (const label of ['a', 'b', 'c']) {
      stack.push({
        label,
        undo: async () => {
          seen.push(label);
        },
      });
    }

    expect(stack.size).toBe(2);
    await stack.pop()?.undo();
    await stack.pop()?.undo();
    expect(seen).toEqual(['c', 'b']);
    expect(stack.pop()).toBeUndefined();
  });
});
