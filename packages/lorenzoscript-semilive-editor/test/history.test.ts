import { expect, it } from 'vitest';
import { History } from '../src/history';

it('undoes and redoes whole texts, and forgets the future after a new change', () => {
  const h = new History();
  h.push('a');
  h.push('ab');
  expect(h.undo('abc')).toBe('ab');
  expect(h.undo('ab')).toBe('a');
  expect(h.undo('a')).toBeNull();
  expect(h.redo('a')).toBe('ab');
  h.push('ab');
  expect(h.canRedo).toBe(false);
});
