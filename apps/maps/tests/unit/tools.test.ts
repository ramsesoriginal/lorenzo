import { expect, test } from 'vitest';
import {
  createOptionValues,
  GROUPS,
  numberFor,
  optionsOf,
  SNAP,
  searchTools,
  TENSION,
  TOLERANCE,
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
  expect(usable(toolByKey('t') as never, plain)).toBe(false);
  expect(usable(toolByKey('f') as never, plain)).toBe(true);
  expect(usable(toolByKey('f') as never, { grid: false, sphere: true })).toBe(false);
  expect(usable(toolByKey('s') as never, plain)).toBe(true);
  expect(usable(toolByKey('s') as never, { grid: false, sphere: true })).toBe(false);
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
  expect(optionsOf(spline, { grid: false })).toEqual([TENSION]);
  expect(optionsOf(toolById('freehand') as ToolDecl, { grid: true })).toEqual([TOLERANCE]);
  expect(optionsOf(toolById('height-line') as ToolDecl, { grid: true })).toEqual([]);

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

test('a number option keeps a value to its range and its step', () => {
  expect(numberFor(TENSION, 0.5)).toBe(0.5);
  expect(numberFor(TENSION, 0.42)).toBe(0.4);
  expect(numberFor(TENSION, 0.99)).toBe(1);
  expect(numberFor(TENSION, 1.01)).toBeNull();
  expect(numberFor(TENSION, -0.01)).toBeNull();
  expect(numberFor(TENSION, Number.NaN)).toBeNull();

  const values = createOptionValues();
  const spline = toolById('spline') as ToolDecl;

  expect(values.get(spline, TENSION)).toBe(0.5);
  values.set(spline, TENSION, 0.2);
  expect(values.get(spline, TENSION)).toBe(0.2);
});
