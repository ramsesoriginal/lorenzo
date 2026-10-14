import { describe, expect, it } from 'vitest';
import {
  ENTRY_PAGE_SIZE,
  kindsLine,
  listCount,
  NO_TEXT,
  offersAllEntries,
  PREVIEW_OFF,
  PREVIEW_OFF_HOLDER,
  parentsText,
  pickDescription,
  preferredLocales,
  previewLine,
  SHOWCASE_EMPTY,
  statGroups,
  statValueText,
  TEXT_NOT_OPEN,
  textLines,
  textNote,
} from '../../src/lib/preview';
import type { PreviewEntityOut, PreviewOut } from '../../src/lib/types';

function entry(overrides: Partial<PreviewEntityOut> = {}): PreviewEntityOut {
  return {
    id: '1',
    name: 'Owlbear',
    kinds: ['item'],
    parents: [],
    featured: true,
    text_visible: true,
    information: [],
    stats: [],
    ...overrides,
  };
}

function preview(level: PreviewOut['preview'], entries: PreviewEntityOut[] = []): PreviewOut {
  return { preview: level, entries };
}

describe('the line a level says', () => {
  it('says a quiet line for a visitor where the switch is off', () => {
    expect(previewLine(preview('off'), 'visitor')).toBe(PREVIEW_OFF);
    expect(PREVIEW_OFF).toBe('The Owner has not opened this repository for a look inside.');
  });

  it('says it of a holder in its own words, and that the names are there', () => {
    expect(previewLine(preview('off'), 'holder')).toBe(PREVIEW_OFF_HOLDER);
    expect(PREVIEW_OFF_HOLDER).toContain('names of its entries');
  });

  it('says nothing was chosen yet where the showcase has no entry', () => {
    expect(previewLine(preview('showcase'), 'visitor')).toBe(SHOWCASE_EMPTY);
    expect(SHOWCASE_EMPTY).toBe('The Owner has not chosen entries to show yet.');
    expect(previewLine(preview('showcase'), 'holder')).toBe(SHOWCASE_EMPTY);
  });

  it('says nothing where there is something to show', () => {
    expect(previewLine(preview('showcase', [entry()]), 'visitor')).toBeNull();
    // At public the list of every entry is there, featured or not.
    expect(previewLine(preview('public'), 'visitor')).toBeNull();
  });
});

describe('the list of every entry', () => {
  it('is a visitor`s at public and no one else`s', () => {
    expect(offersAllEntries(preview('public'), 'visitor')).toBe(true);
    expect(offersAllEntries(preview('showcase'), 'visitor')).toBe(false);
    expect(offersAllEntries(preview('off'), 'visitor')).toBe(false);
    expect(offersAllEntries(preview('public'), 'holder')).toBe(false);
  });

  it('counts what is shown of what there is', () => {
    expect(ENTRY_PAGE_SIZE).toBeLessThanOrEqual(50);
    expect(listCount(20, 134)).toBe('20 of 134 entries');
    expect(listCount(134, 134)).toBe('134 entries');
    expect(listCount(1, 1)).toBe('1 entry');
  });
});

describe('an entry`s lines', () => {
  it('names its kinds as people read them', () => {
    expect(kindsLine(entry({ kinds: ['item', 'being'] }))).toBe('Item, Being');
    expect(kindsLine(entry({ kinds: ['item_instance'] }))).toBe('Inventory item');
  });

  it('names its parents, and says nothing of none', () => {
    expect(parentsText(entry())).toBeNull();
    expect(
      parentsText(
        entry({
          parents: [
            { id: 'a', name: 'Weapon' },
            { id: 'b', name: 'Magic' },
          ],
        }),
      ),
    ).toBe('Inherits from Weapon, Magic');
  });

  it('reads a value as a person does', () => {
    expect(statValueText(3)).toBe('3');
    expect(statValueText(2.5)).toBe('2.5');
    expect(statValueText(true)).toBe('Yes');
    expect(statValueText(false)).toBe('No');
    expect(statValueText('Fire')).toBe('Fire');
    expect(statValueText(null)).toBe('');
  });

  it('groups the stat values by group in the order given', () => {
    expect(
      statGroups([
        { definition_id: '1', name: 'Weight', group: 'Physical', value: 4 },
        { definition_id: '2', name: 'Damage', group: 'Combat', value: '1d8' },
        { definition_id: '3', name: 'Size', group: 'Physical', value: 'Large' },
        { definition_id: '4', name: 'Magic', group: 'Combat', value: true },
      ]),
    ).toEqual([
      {
        group: 'Physical',
        stats: [
          { name: 'Weight', value: '4' },
          { name: 'Size', value: 'Large' },
        ],
      },
      {
        group: 'Combat',
        stats: [
          { name: 'Damage', value: '1d8' },
          { name: 'Magic', value: 'Yes' },
        ],
      },
    ]);
    expect(statGroups([])).toEqual([]);
  });
});

describe('the description a reader`s language picks', () => {
  const descriptions = [
    { locale: 'en-US', content: 'A beast.' },
    { locale: 'de-DE', content: 'Ein Tier.' },
    { locale: 'fr-FR', content: 'Une bete.' },
  ];

  it('takes the exact locale first', () => {
    expect(pickDescription(descriptions, ['de-DE', 'en-US'])?.content).toBe('Ein Tier.');
  });

  it('takes the same language of another region next', () => {
    expect(pickDescription(descriptions, ['fr-CA'])?.content).toBe('Une bete.');
    expect(pickDescription(descriptions, ['de'])?.content).toBe('Ein Tier.');
  });

  it('takes the first where nothing fits, and nothing where there is no text', () => {
    expect(pickDescription(descriptions, ['ja-JP'])?.content).toBe('A beast.');
    expect(pickDescription(descriptions, [])?.content).toBe('A beast.');
    expect(pickDescription([], ['en'])).toBeNull();
  });

  it('prefers the language the reader put first', () => {
    expect(pickDescription(descriptions, ['fr', 'de'])?.content).toBe('Une bete.');
  });

  it('reads the browser`s languages as they are', () => {
    expect(preferredLocales(['de-DE', ' ', 'en'])).toEqual(['de-DE', 'en']);
    expect(preferredLocales(undefined)).toEqual([]);
  });
});

describe('an entry`s text rows', () => {
  it('shows each row by its title with the text the reader`s language picks', () => {
    const rows = textLines(
      entry({
        information: [
          {
            id: 'r1',
            title: 'Habits',
            type: 'note',
            descriptions: [
              { locale: 'en-US', content: 'Hunts at night.' },
              { locale: 'de-DE', content: 'Jagt nachts.' },
            ],
            pictures: [{ id: 'p1', file_type: 'image/png' }],
          },
          { id: 'r2', title: 'Empty', type: 'note', descriptions: [], pictures: [] },
        ],
      }),
      ['de'],
    );

    expect(rows).toEqual([
      {
        id: 'r1',
        title: 'Habits',
        text: 'Jagt nachts.',
        pictures: [{ id: 'p1', file_type: 'image/png' }],
      },
      { id: 'r2', title: 'Empty', text: '', pictures: [] },
    ]);
  });

  it('says why an entry shows no text', () => {
    expect(textNote(entry({ text_visible: false }))).toBe(TEXT_NOT_OPEN);
    expect(textNote(entry({ information: [], stats: [] }))).toBe(NO_TEXT);
    expect(
      textNote(
        entry({
          stats: [{ definition_id: '1', name: 'Weight', group: 'Physical', value: 1 }],
        }),
      ),
    ).toBeNull();
    expect(
      textNote(
        entry({
          information: [{ id: 'r', title: 'Habits', type: 'note', descriptions: [], pictures: [] }],
        }),
      ),
    ).toBeNull();
  });
});

describe('the words', () => {
  it('never say tenant, grant or subscription', () => {
    const said = [PREVIEW_OFF, PREVIEW_OFF_HOLDER, SHOWCASE_EMPTY, TEXT_NOT_OPEN, NO_TEXT].join(
      ' ',
    );

    expect(said).not.toMatch(/tenant|grant|subscription|stable|frozen/i);
  });
});
