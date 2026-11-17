import { describe, expect, it } from 'vitest';
import { freshTimer, remainingTime, storedTimer } from './writing-timer';

describe('personal timer recovery', () => {
  it('uses its deadline after delayed callbacks and clamps clock changes', () => {
    const state = { ...freshTimer(1), started: true, deadline: 100_000 };
    expect(remainingTime(state, 50_000)).toBe(50_000);
    expect(remainingTime(state, 110_000)).toBe(0);
    expect(remainingTime(state, 0)).toBe(60_000);
    expect(remainingTime({ ...state, deadline: null, remaining: 25_000 }, 999_999)).toBe(25_000);
  });
  it('restores a paused timer and rejects malformed or out-of-range state', () => {
    const state = { ...freshTimer(2), started: true, remaining: 9000 };
    expect(storedTimer(JSON.stringify(state))).toEqual(state);
    for (const value of [
      null,
      '{',
      '{}',
      'false',
      JSON.stringify({ ...state, duration: 0 }),
      JSON.stringify({ ...state, remaining: -1 }),
      JSON.stringify({ ...state, deadline: 'soon' }),
      JSON.stringify({ ...state, duration: 1441 * 60_000 }),
    ])
      expect(storedTimer(value)).toEqual(freshTimer());
  });
});
