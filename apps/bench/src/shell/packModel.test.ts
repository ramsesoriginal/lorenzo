import { describe, expect, it } from 'vitest';
import { indent, move, outdent, parsePack, type Row, remove, total, writePack } from './packModel';

const TEXT = `This pack contains:

- 1 x [Backpack](bag)
  - 5 x [Rations (1 day)](rations)
  - 2 x [Torch](torch)
- 1 x Alms box

Kept with care.`;

const row = (depth: number, label: string, count = 1): Row => ({
  depth,
  count,
  label,
  slug: label.toLowerCase(),
});

describe('parsePack', () => {
  it('reads the list, and keeps the prose around it', () => {
    const p = parsePack(TEXT);
    expect(p.rows.map((r) => [r.depth, r.count, r.label, r.slug])).toEqual([
      [0, 1, 'Backpack', 'bag'],
      [1, 5, 'Rations (1 day)', 'rations'],
      [1, 2, 'Torch', 'torch'],
      [0, 1, 'Alms box', null],
    ]);
    expect(p.before).toEqual(['This pack contains:', '']);
    expect(p.after).toEqual(['', 'Kept with care.']);
    expect(p.mixed).toBe(false);
  });
  it('writes the same text back', () => {
    expect(writePack(parsePack(TEXT))).toBe(TEXT);
  });
  it('has no rows in a text without a list', () => {
    const p = parsePack('Just a sentence.');
    expect(p.rows).toEqual([]);
    expect(writePack(p)).toBe('Just a sentence.');
  });
  it('knows when other text is between the rows', () => {
    expect(parsePack('- 1 x [A](a)\nnote\n- 1 x [B](b)').mixed).toBe(true);
  });
  it('reads a mis-indented line as no row', () => {
    expect(parsePack('- 1 x [A](a)\n - 1 x [B](b)').rows).toHaveLength(1);
  });
});

describe('moving rows', () => {
  const rows = [row(0, 'A'), row(1, 'A1'), row(0, 'B'), row(1, 'B1'), row(0, 'C')];
  const names = (r: readonly Row[]) => r.map((x) => x.label);
  it('moves a row with what is inside it past its neighbour', () => {
    expect(names(move(rows, 2, -1).rows)).toEqual(['B', 'B1', 'A', 'A1', 'C']);
    expect(names(move(rows, 0, 1).rows)).toEqual(['B', 'B1', 'A', 'A1', 'C']);
  });
  it('stops at the ends of its level', () => {
    expect(names(move(rows, 0, -1).rows)).toEqual(names(rows));
    expect(names(move(rows, 4, 1).rows)).toEqual(names(rows));
    expect(names(move(rows, 1, 1).rows)).toEqual(names(rows));
  });
  it('indents into the row above, and out again', () => {
    const into = indent(rows, 2);
    expect(into.map((r) => r.depth)).toEqual([0, 1, 1, 2, 0]);
    expect(outdent(into, 2).map((r) => r.depth)).toEqual([0, 1, 0, 1, 0]);
  });
  it('does not indent the first row, or past three levels', () => {
    expect(indent(rows, 0).map((r) => r.depth)).toEqual([0, 1, 0, 1, 0]);
    const deep = [row(0, 'A'), row(1, 'B'), row(2, 'C')];
    expect(indent(deep, 1).map((r) => r.depth)).toEqual([0, 1, 2]);
  });
  it('removing a container lifts what it held', () => {
    expect(remove(rows, 0).map((r) => [r.label, r.depth])).toEqual([
      ['A1', 0],
      ['B', 0],
      ['B1', 1],
      ['C', 0],
    ]);
  });
});

describe('total', () => {
  it('multiplies by the containers it is in', () => {
    const rows = [
      row(0, 'Bag', 2),
      row(1, 'Rope', 3),
      row(0, 'Torch', 1),
      { ...row(0, 'x'), slug: null },
    ];
    const w: Record<string, number> = { bag: 5, rope: 1, torch: 1 };
    expect(total(rows, (s) => w[s])).toEqual({
      weight: 2 * 5 + 2 * 3 * 1 + 1,
      known: 3,
      listed: 4,
    });
  });
});
