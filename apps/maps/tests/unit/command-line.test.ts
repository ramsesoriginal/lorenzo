import { describe, expect, it } from 'vitest';
import { parseCommand, parsePoint } from '../../src/lib/command-line';
import { TOOLS } from '../../src/lib/tools';

const flat = { grid: false, sphere: false };

describe('the command line', () => {
  it('reads points', () => {
    expect(parsePoint('120,80')).toEqual([120, 80]);
    expect(parsePoint(' -3.5 , 4 ')).toEqual([-3.5, 4]);
    expect(parsePoint('x,1')).toBeNull();
  });

  it('reads the plain commands, whatever their case', () => {
    expect(parseCommand('UNDO', TOOLS, flat)).toEqual({ kind: 'undo' });
    expect(parseCommand('redo', TOOLS, flat)).toEqual({ kind: 'redo' });
    expect(parseCommand('Fit', TOOLS, flat)).toEqual({ kind: 'fit' });
    expect(parseCommand('help', TOOLS, flat)).toEqual({ kind: 'help' });
    expect(parseCommand('   ', TOOLS, flat)).toBeNull();
  });

  it('reads a bare point as the next point, and DONE', () => {
    expect(parseCommand('120,80', TOOLS, flat)).toEqual({ kind: 'point', at: [120, 80] });
    expect(parseCommand('done', TOOLS, flat)).toEqual({ kind: 'done' });
  });

  it('reads PLACE with a name of several words and a point, and SELECT with a name', () => {
    expect(parseCommand('PLACE Old Town 12,7', TOOLS, flat)).toEqual({
      kind: 'place',
      name: 'Old Town',
      at: [12, 7],
    });
    expect(parseCommand('place Harbour', TOOLS, flat)?.kind).toBe('error');
    expect(parseCommand('select Old Town', TOOLS, flat)).toEqual({
      kind: 'select',
      name: 'Old Town',
    });
    expect(parseCommand('select', TOOLS, flat)?.kind).toBe('error');
  });

  it('takes a tool by its name, says a planned one is planned and one the Map cannot use', () => {
    expect(parseCommand('line', TOOLS, flat)).toMatchObject({ kind: 'tool' });
    expect(parseCommand('Spline', TOOLS, flat)).toMatchObject({ kind: 'planned' });
    expect(parseCommand('cells', TOOLS, flat)).toMatchObject({ kind: 'unavailable' });
    expect(parseCommand('cells', TOOLS, { grid: true, sphere: false })).toMatchObject({
      kind: 'tool',
    });
    expect(parseCommand('nonsense', TOOLS, flat)?.kind).toBe('error');
  });
});
