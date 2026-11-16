import { describe, expect, it } from 'vitest';
import { createHistory } from '../../src/lib/history';

const step = (entry: string) => [{ entry, before: null, after: null }];

describe('history entries', () => {
  it('names each step and keeps the undone ones listed until something new is done', () => {
    const history = createHistory();
    history.record(step('a'), 'Placed A');
    history.record(step('b'), 'Placed B');
    expect(history.entries()).toEqual([
      { name: 'Placed A', done: true },
      { name: 'Placed B', done: true },
    ]);
    expect(history.position()).toBe(2);
    history.undo();
    expect(history.entries()[1]).toEqual({ name: 'Placed B', done: false });
    expect(history.position()).toBe(1);
    history.record(step('c'), 'Placed C');
    expect(history.entries().map((e) => e.name)).toEqual(['Placed A', 'Placed C']);
  });
});
