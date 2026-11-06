import { expect, test } from 'vitest';
import { relationshipSentence } from './relationshipWords';

const row = { name: 'Mara honors Wren', end_a: { name: 'Mara' }, end_b: { name: 'Wren' } };

test('a relationship is told in words, with its direction', () => {
  expect(relationshipSentence({ ...row, one_way: true })).toBe(
    'Mara honors Wren: From Mara to Wren.',
  );
  expect(relationshipSentence({ ...row, one_way: false })).toBe(
    'Mara honors Wren: Between Mara and Wren, both ways.',
  );
});
