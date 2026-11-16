import { expect, test } from 'vitest';
import {
  createOptionValues,
  GROUPS,
  optionsOf,
  SNAP,
  searchTools,
  TOOLS,
  type ToolDecl,
  toolById,
  toolByKey,
  toolsOf,
  usable,
} from '../../src/lib/tools';

test('every tool has its own key, a group and a reason when it is planned', () => {
  const keys = TOOLS.map((tool) => tool.key);
  expect(new Set(keys).size).toBe(keys.length);
  for (const tool of TOOLS) {
    expect(GROUPS).toContain(tool.group);
    if (tool.state === 'planned') expect(tool.reason).toBeTruthy();
  }
  expect(TOOLS).toHaveLength(13);
});

test('a key finds its tool, in either case', () => {
  expect(toolByKey('P')?.id).toBe('pin');
  expect(toolByKey('g')?.id).toBe('cells');
  expect(toolByKey('1')).toBeUndefined();
});

test('the groups hold the tools the design lists', () => {
  expect(toolsOf('select').map((t) => t.id)).toEqual(['select']);
  expect(toolsOf('place').map((t) => t.id)).toEqual(['pin', 'circle']);
  expect(toolsOf('draw').map((t) => t.id)).toEqual(['line', 'spline', 'freehand', 'area', 'cells']);
  expect(toolsOf('terrain')).toHaveLength(2);
  expect(toolsOf('generate')).toHaveLength(3);
});

test('a search finds a tool by name, group or key', () => {
  expect(searchTools('').length).toBe(13);
  expect(searchTools('cave').map((t) => t.id)).toEqual(['cave-system']);
  expect(searchTools('terrain').map((t) => t.id)).toEqual(['height-line', 'height-brush']);
  expect(searchTools('fill wave').map((t) => t.id)).toEqual(['wave-function-collapse']);
  expect(searchTools('nothing like it')).toEqual([]);
});

test('a planned tool is never usable, and a grid tool needs a grid and a circle no sphere', () => {
  const plain = { grid: false, sphere: false };
  expect(usable(toolByKey('s') as never, plain)).toBe(false);
  expect(usable(toolByKey('g') as never, plain)).toBe(false);
  expect(usable(toolByKey('g') as never, { grid: true, sphere: false })).toBe(true);
  expect(usable(toolByKey('c') as never, { grid: false, sphere: true })).toBe(false);
  expect(usable(toolByKey('c') as never, plain)).toBe(true);
});

test('lists the options of a tool, and offers one that needs a grid only with a grid (ADR 0470)', () => {
  const line = toolById('line') as ToolDecl;
  const spline = toolById('spline') as ToolDecl;

  expect(optionsOf(line, { grid: true })).toEqual([SNAP]);
  expect(optionsOf(line, { grid: false })).toEqual([]);
  expect(optionsOf(spline, { grid: true })).toEqual([]);

  const words = TOOLS.flatMap((tool) => (tool.options ?? []).map((o) => `${tool.id} ${o.word}`));

  expect(new Set(words).size).toBe(words.length);
  for (const tool of TOOLS) {
    for (const option of tool.options ?? []) expect(option.word).toMatch(/^[a-z]+$/);
  }
});

test('keeps what an option is set to, one value for every tool when it is shared', () => {
  const values = createOptionValues();
  const line = toolById('line') as ToolDecl;
  const area = toolById('area') as ToolDecl;
  const own = { ...SNAP, id: 'own', shared: false };

  expect(values.get(line, SNAP)).toBe(true);
  values.set(line, SNAP, false);
  expect(values.get(area, SNAP)).toBe(false);
  values.set(line, own, false);
  expect(values.get(line, own)).toBe(false);
  expect(values.get(area, own)).toBe(true);
});
