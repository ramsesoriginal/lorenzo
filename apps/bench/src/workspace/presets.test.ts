import { describe, expect, it } from 'vitest';
import {
  emptyWorkspace,
  floatOut,
  group,
  locate,
  normalize,
  treeGroups,
  type Workspace,
} from './model';
import { activePreset, applyPreset } from './presets';

const base = (): Workspace => ({
  ...emptyWorkspace(),
  tree: normalize({
    t: 's',
    id: 's-x',
    dir: 'row',
    ratios: [0.5, 0.5],
    kids: [group('a', ['explorer']), group('b', ['entry', 'grid'])],
  }),
});
const groupsOf = (ws: Workspace) => treeGroups(ws.tree).map((g) => g.panes);

describe('presets', () => {
  it('Write is the entry alone, with the panes that are not the preset’s own', () => {
    expect(groupsOf(applyPreset(base(), 'write'))).toEqual([['entry', 'grid']]);
  });

  it('Inspect is the explorer, the entry and the stats and links, side by side', () => {
    expect(groupsOf(applyPreset(base(), 'inspect'))).toEqual([
      ['explorer'],
      ['entry', 'grid'],
      ['props', 'links'],
    ]);
  });

  it('Compare is the explorer, the entry and stats over the table and the ancestry graph', () => {
    expect(groupsOf(applyPreset(base(), 'compare'))).toEqual([
      ['explorer'],
      ['entry', 'grid'],
      ['props', 'links'],
      ['table'],
      ['ancestry'],
    ]);
  });

  it('leaves a pane that is in a floating window where it is', () => {
    const floated = floatOut(base(), ['explorer'], 'explorer', 10, 10).ws;
    const ws = applyPreset(floated, 'inspect');
    expect(groupsOf(ws)).toEqual([
      ['entry', 'grid'],
      ['props', 'links'],
    ]);
    expect(locate(ws, 'explorer')?.kind).toBe('float');
  });

  it('is repeatable: a preset applied to its own result changes nothing', () => {
    for (const name of ['write', 'inspect', 'compare'] as const) {
      const once = applyPreset(base(), name);
      expect(applyPreset(once, name).tree).toEqual(once.tree);
    }
  });
});

describe('which preset a workspace is', () => {
  it('knows each preset it made, whatever the sizes', () => {
    for (const name of ['write', 'inspect', 'compare'] as const) {
      const ws = applyPreset(base(), name);
      expect(activePreset(ws)).toBe(name);
      const tree = ws.tree;
      if (tree?.t === 's') {
        const even = tree.kids.map(() => 1 / tree.kids.length);
        expect(activePreset({ ...ws, tree: { ...tree, ratios: even } })).toBe(name);
      }
    }
  });

  it('is none once the panes are moved by hand', () => {
    const ws = applyPreset(base(), 'inspect');
    const moved = {
      ...ws,
      tree: normalize({
        t: 's',
        id: 's-m',
        dir: 'row',
        ratios: [0.5, 0.5],
        kids: [group('a', ['explorer', 'props']), group('b', ['entry', 'grid', 'links'])],
      }),
    } as Workspace;
    expect(activePreset(moved)).toBeNull();
  });
});
