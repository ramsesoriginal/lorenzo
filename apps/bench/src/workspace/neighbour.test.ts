import { describe, expect, it } from 'vitest';
import { type Box, neighbourGroup } from './neighbour';

// Explorer | Entry over Table | Stats, as in the Write layout.
const boxes: Box[] = [
  { id: 'a', x: 0, y: 0, w: 0.25, h: 1 },
  { id: 'b', x: 0.25, y: 0, w: 0.5, h: 0.7 },
  { id: 'c', x: 0.25, y: 0.7, w: 0.5, h: 0.3 },
  { id: 'd', x: 0.75, y: 0, w: 0.25, h: 1 },
];

describe('neighbourGroup', () => {
  it('finds the group beside, above and below', () => {
    expect(neighbourGroup(boxes, 'b', 'right')).toBe('d');
    expect(neighbourGroup(boxes, 'b', 'left')).toBe('a');
    expect(neighbourGroup(boxes, 'b', 'bottom')).toBe('c');
    expect(neighbourGroup(boxes, 'c', 'top')).toBe('b');
  });
  it('is null at the edge', () => {
    expect(neighbourGroup(boxes, 'a', 'left')).toBeNull();
    expect(neighbourGroup(boxes, 'b', 'top')).toBeNull();
  });
  it('takes the one that overlaps most when several are beside', () => {
    expect(neighbourGroup(boxes, 'a', 'right')).toBe('b');
    expect(neighbourGroup(boxes, 'd', 'left')).toBe('b');
  });
  it('is null for a group it does not know', () => {
    expect(neighbourGroup(boxes, 'z', 'left')).toBeNull();
  });
});
