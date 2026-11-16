import { describe, expect, it } from 'vitest';

import {
  HIDDEN_SOURCE_LABEL,
  hasOwnText,
  isFromHiddenEntry,
  isOwnText,
  textHome,
  textSources,
} from './textSources';

const longsword = { id: 'sword-id', name: 'Longsword', slug: 'longsword', kinds: ['item'] };
const ENTRY = 'entry-id';

// What the API sends: null `from_entity` for the item's own, or for a hidden entry's text
// with `from_hidden: true` (ADR 0437); older answers have no `from_hidden` at all.
const own = { from_entity: null };
const ownNull = { from_entity: null, from_hidden: null };
const inherited = { from_entity: longsword };
const hidden = { from_entity: null, from_hidden: true };

describe('isOwnText / isFromHiddenEntry', () => {
  it('reads a null from_entity with no from_hidden as the item’s own, as before', () => {
    expect(isOwnText(own)).toBe(true);
    expect(isOwnText(ownNull)).toBe(true);
    expect(isOwnText({})).toBe(true);
    expect(isFromHiddenEntry(own)).toBe(false);
    expect(isFromHiddenEntry(ownNull)).toBe(false);
  });

  it('does not read a text from a hidden entry as the item’s own', () => {
    expect(isOwnText(hidden)).toBe(false);
    expect(isFromHiddenEntry(hidden)).toBe(true);
  });

  it('reads a named source as inherited', () => {
    expect(isOwnText(inherited)).toBe(false);
    expect(isFromHiddenEntry(inherited)).toBe(false);
  });
});

describe('hasOwnText', () => {
  it('is false when the only text is inherited from a hidden entry', () => {
    expect(hasOwnText([hidden])).toBe(false);
    expect(hasOwnText([hidden, inherited])).toBe(false);
  });

  it('is true when the item has its own next to a hidden one', () => {
    expect(hasOwnText([hidden, own])).toBe(true);
    expect(hasOwnText([ownNull])).toBe(true);
  });

  it('is false with no texts', () => {
    expect(hasOwnText([])).toBe(false);
  });
});

describe('textHome', () => {
  it('is the ancestor for a named source, and the item otherwise', () => {
    expect(textHome(inherited, ENTRY)).toBe('sword-id');
    expect(textHome(own, ENTRY)).toBe(ENTRY);
    expect(textHome(hidden, ENTRY)).toBe(ENTRY);
  });
});

describe('textSources', () => {
  it('lists the item’s own first, then each named source once, in order', () => {
    const other = { id: 'other-id', name: 'Weapon', slug: 'weapon', kinds: ['item'] };
    expect(
      textSources(ENTRY, [
        inherited,
        { from_entity: other },
        inherited,
        { from_entity: longsword },
      ]),
    ).toEqual([
      { kind: 'own', id: ENTRY },
      { kind: 'entry', id: 'sword-id', source: longsword },
      { kind: 'entry', id: 'other-id', source: other },
    ]);
  });

  it('lists hidden entries as one unnamed group, in place', () => {
    expect(textSources(ENTRY, [inherited, hidden, hidden])).toEqual([
      { kind: 'own', id: ENTRY },
      { kind: 'entry', id: 'sword-id', source: longsword },
      { kind: 'hidden' },
    ]);
  });

  it('does not give a hidden group for texts that are the item’s own', () => {
    expect(textSources(ENTRY, [own, ownNull, {}])).toEqual([{ kind: 'own', id: ENTRY }]);
  });

  it('carries no id or name for the hidden group', () => {
    const [, group] = textSources(ENTRY, [hidden]);
    expect(JSON.stringify(group)).toBe('{"kind":"hidden"}');
  });
});

describe('HIDDEN_SOURCE_LABEL', () => {
  it('is the brand’s wording, with no name', () => {
    expect(HIDDEN_SOURCE_LABEL).toBe('From a hidden entry');
  });
});
