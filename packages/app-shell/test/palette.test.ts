import { describe, expect, it, vi } from 'vitest';
import { createKeymap, goChord, type KeyInput } from '../src/keys';
import {
  flatten,
  matchRanges,
  moveSelection,
  nextScope,
  type PaletteItem,
  pushRecent,
  search,
} from '../src/palette';

const item = (
  over: Partial<PaletteItem> & Pick<PaletteItem, 'id' | 'name' | 'group'>,
): PaletteItem => ({
  run: () => {},
  ...over,
});

const items: PaletteItem[] = [
  item({
    id: 'entry:mara',
    group: 'Entries',
    name: 'Mara Quill',
    kind: 'Character',
    app: 'Beings',
  }),
  item({
    id: 'entry:harbour',
    group: 'Entries',
    name: 'Harbour master',
    kind: 'NPC',
    app: 'Beings',
  }),
  item({
    id: 'entry:map',
    group: 'Entries',
    name: 'Map of the outer ring',
    kind: 'Map',
    app: 'Maps',
  }),
  item({ id: 'app:maps', group: 'Go to', name: 'Maps', kind: 'Open the app', keys: 'G M' }),
  item({ id: 'app:beings', group: 'Go to', name: 'Beings', kind: 'Open the app', keys: 'G B' }),
  item({ id: 'a.new', group: 'Actions', name: 'New being…', keywords: ['create', 'character'] }),
  item({ id: 'a.theme', group: 'Actions', name: 'Change theme' }),
];

const names = (sections: ReturnType<typeof search>) =>
  sections.map((s) => [s.group, s.rows.map((r) => r.item.name)]);

describe('search', () => {
  it('with no query lists the apps and the actions, and no entries', () => {
    expect(names(search(items, '', 'Everything'))).toEqual([
      ['Go to', ['Maps', 'Beings']],
      ['Actions', ['New being…', 'Change theme']],
    ]);
  });

  it('puts the recent ones first when nothing is typed, and not when something is', () => {
    expect(names(search(items, '', 'Everything', ['a.theme', 'gone', 'app:maps']))[0]).toEqual([
      'Recent',
      ['Change theme', 'Maps'],
    ]);
    expect(search(items, 'ma', 'Everything', ['a.theme']).some((s) => s.group === 'Recent')).toBe(
      false,
    );
  });

  it('finds across the groups, a name that starts with the query before one that only contains it', () => {
    const sections = search(items, 'ma', 'Everything');

    expect(names(sections)).toEqual([
      ['Entries', ['Mara Quill', 'Map of the outer ring', 'Harbour master']],
      ['Go to', ['Maps']],
    ]);
  });

  it('matches a keyword that is not in the name, without marking anything', () => {
    const rows = flatten(search(items, 'create', 'Everything'));

    expect(rows.map((r) => r.item.name)).toEqual(['New being…']);
    expect(rows[0]?.ranges).toEqual([]);
  });

  it('needs every word of a query', () => {
    expect(flatten(search(items, 'mara quill', 'Everything')).map((r) => r.item.id)).toEqual([
      'entry:mara',
    ]);
    expect(flatten(search(items, 'mara zzz', 'Everything'))).toEqual([]);
  });

  it('narrows to a scope', () => {
    expect(names(search(items, '', 'Apps'))).toEqual([['Go to', ['Maps', 'Beings']]]);
    expect(names(search(items, '', 'Actions'))).toEqual([
      ['Actions', ['New being…', 'Change theme']],
    ]);
    expect(names(search(items, 'ma', 'Entries'))).toEqual([
      ['Entries', ['Mara Quill', 'Map of the outer ring', 'Harbour master']],
    ]);
  });

  it('shows at most six entries', () => {
    const many = Array.from({ length: 10 }, (_, i) =>
      item({ id: `e${i}`, group: 'Entries', name: `Thing ${i}` }),
    );

    expect(flatten(search(many, 'thing', 'Everything'))).toHaveLength(6);
  });
});

describe('matchRanges', () => {
  it('marks each word where it is, and merges what touches', () => {
    expect(matchRanges('Mara Quill', 'ma qu')).toEqual([
      [0, 2],
      [5, 7],
    ]);
    expect(matchRanges('Mara', 'ma ra')).toEqual([[0, 4]]);
    expect(matchRanges('Mara', '')).toEqual([]);
  });
});

describe('the selection and the scopes', () => {
  it('wraps at both ends, and with nothing to select stays at 0', () => {
    expect(moveSelection(0, -1, 3)).toBe(2);
    expect(moveSelection(2, 1, 3)).toBe(0);
    expect(moveSelection(5, 0, 0)).toBe(0);
  });

  it('goes through the scopes with Tab and back with Shift Tab', () => {
    expect(nextScope('Everything')).toBe('Entries');
    expect(nextScope('Actions')).toBe('Everything');
    expect(nextScope('Everything', -1)).toBe('Actions');
  });

  it('remembers three, newest first, without repeats', () => {
    expect(pushRecent(['a', 'b', 'c'], 'd')).toEqual(['d', 'a', 'b']);
    expect(pushRecent(['a', 'b'], 'b')).toEqual(['b', 'a']);
  });
});

describe('the keymap', () => {
  const key = (k: string, over: Partial<KeyInput> = {}): KeyInput => ({
    key: k,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    shiftKey: false,
    typing: false,
    ...over,
  });

  function map(on = true) {
    let t = 0;
    const calls = { go: vi.fn(), help: vi.fn(), palette: vi.fn() };
    const keymap = createKeymap({
      singleKeys: () => on,
      onGo: calls.go,
      onHelp: calls.help,
      onPalette: calls.palette,
      now: () => t,
    });

    return { keymap, calls, wait: (ms: number) => (t += ms) };
  }

  it('Ctrl K and Cmd K open the palette, also in a field and with single keys off', () => {
    const { keymap, calls } = map(false);

    expect(keymap.handle(key('k', { ctrlKey: true, typing: true }))).toBe(true);
    expect(keymap.handle(key('K', { metaKey: true }))).toBe(true);
    expect(calls.palette).toHaveBeenCalledTimes(2);
  });

  it('G then a letter goes there, within a moment', () => {
    const { keymap, calls, wait } = map();

    expect(keymap.handle(key('g'))).toBe(true);
    expect(keymap.handle(key('s'))).toBe(true);
    expect(calls.go).toHaveBeenCalledWith('sessions');

    keymap.handle(key('g'));
    wait(2000);
    expect(keymap.handle(key('s'))).toBe(false);
    expect(calls.go).toHaveBeenCalledTimes(1);
  });

  it('G then a key that goes nowhere does nothing, and G alone changes nothing else', () => {
    const { keymap, calls } = map();

    keymap.handle(key('g'));
    expect(keymap.handle(key('z'))).toBe(false);
    expect(calls.go).not.toHaveBeenCalled();
  });

  it('? lists the shortcuts', () => {
    const { keymap, calls } = map();

    expect(keymap.handle(key('?', { shiftKey: true }))).toBe(true);
    expect(calls.help).toHaveBeenCalledOnce();
  });

  it('leaves a key typed into a field alone', () => {
    const { keymap, calls } = map();

    expect(keymap.handle(key('g', { typing: true }))).toBe(false);
    expect(keymap.handle(key('?', { typing: true }))).toBe(false);
    expect(calls.help).not.toHaveBeenCalled();
  });

  it('with the single keys off, G and ? do nothing', () => {
    const { keymap, calls } = map(false);

    expect(keymap.handle(key('g'))).toBe(false);
    expect(keymap.handle(key('?'))).toBe(false);
    expect(calls.help).not.toHaveBeenCalled();
  });

  it('writes a place’s chord for the palette’s hint', () => {
    expect(goChord('sessions')).toBe('G S');
    expect(goChord('account_hub')).toBe('G A');
    expect(goChord('nowhere')).toBeUndefined();
  });
});
