import { expect, it } from 'vitest';
import { readSession } from './writing-session';

it('recovers signed session progress and rejects malformed local state', () => {
  const state = { id: 'a-session', target: 500, net: -12, active: true };
  expect(readSession(JSON.stringify(state))).toEqual(state);
  for (const source of [
    null,
    '{',
    '{}',
    'false',
    JSON.stringify({ ...state, target: 0 }),
    JSON.stringify({ ...state, target: 100_000_001 }),
    JSON.stringify({ ...state, net: '12' }),
    JSON.stringify({ ...state, active: 1 }),
  ])
    expect(readSession(source)).toBeNull();
});
