import { expect, test } from 'vitest';
import type { RelationRow } from '../core/transport';
import { relationModel, relationSentence } from './relationsPane';

const row = (over: Partial<RelationRow> = {}): RelationRow => ({
  id: 'r1',
  name: 'Mara honors Wren',
  oneWay: true,
  endA: { id: 'mara', name: 'Mara' },
  endB: { id: 'wren', name: 'Wren' },
  ...over,
});

test('a relationship is told in words, with its direction', () => {
  expect(relationSentence(row())).toBe('Mara honors Wren: From Mara to Wren.');
  expect(relationSentence(row({ oneWay: false }))).toBe(
    'Mara honors Wren: Between Mara and Wren, both ways.',
  );
});

test('the graph around an entry has the entry and each other end once, and an edge a relationship', () => {
  const model = relationModel({ id: 'mara', name: 'Mara' }, [
    row(),
    row({ id: 'r2', name: 'Rivals', oneWay: false }),
    row({ id: 'r3', endA: { id: 'dren', name: 'Dren' }, endB: { id: 'mara', name: 'Mara' } }),
  ]);
  expect(model.nodes.map((n) => n.id).sort()).toEqual(['dren', 'mara', 'wren']);
  expect(model.edges.map((e) => [e.id, e.directed])).toEqual([
    ['r1', true],
    ['r2', false],
    ['r3', true],
  ]);
});
