import { describe, expect, it } from 'vitest';
import {
  DELETED,
  EMPTY,
  REVIEW_WORDS,
  reviewRows,
  reviewWords,
  valueKind,
  valueText,
} from '../src';

describe('the words', () => {
  it('are the defaults when a host says nothing', () => {
    expect(reviewWords()).toEqual(REVIEW_WORDS);
    expect(reviewWords({})).toEqual(REVIEW_WORDS);
  });

  it('change only what a host overrides', () => {
    const words = reviewWords({ mine: 'Mine', theirs: 'Theirs', keepMine: 'Keep mine' });

    expect(words.mine).toBe('Mine');
    expect(words.theirs).toBe('Theirs');
    expect(words.keepMine).toBe('Keep mine');
    expect(words.was).toBe('Was');
    expect(words.takeTheirs).toBe(REVIEW_WORDS.takeTheirs);
  });

  it('ignore an override that is undefined', () => {
    const words = reviewWords({ mine: undefined } as never);

    expect(words.mine).toBe('Yours');
  });

  it('say the sentences with the field in them', () => {
    expect(REVIEW_WORDS.chooseFor('Name')).toBe('Choose for Name');
    expect(REVIEW_WORDS.keptMine('Name')).toBe('Keeping yours for Name.');
    expect(REVIEW_WORDS.tookTheirs('Name')).toBe('Taking the update for Name.');
  });

  it('are the product words: Was, Now, Yours, Keep yours, Take the update', () => {
    expect(REVIEW_WORDS).toMatchObject({
      was: 'Was',
      theirs: 'Now',
      mine: 'Yours',
      noValue: 'No value',
      deleted: 'Deleted',
      keepMine: 'Keep yours',
      takeTheirs: 'Take the update, and replace yours',
    });
  });
});

describe('a value as text', () => {
  it('is a string as it is, including one that looks like markup', () => {
    expect(valueText('Longsword', REVIEW_WORDS)).toBe('Longsword');
    expect(valueText('<b>x</b>', REVIEW_WORDS)).toBe('<b>x</b>');
    expect(valueText('', REVIEW_WORDS)).toBe('');
  });

  it('says no value and deleted in words, and the host may say them differently', () => {
    expect(valueText(EMPTY, REVIEW_WORDS)).toBe('No value');
    expect(valueText(DELETED, REVIEW_WORDS)).toBe('Deleted');
    expect(valueText(EMPTY, reviewWords({ noValue: 'Nothing' }))).toBe('Nothing');
  });

  it('has a kind', () => {
    expect(valueKind('x')).toBe('text');
    expect(valueKind(EMPTY)).toBe('empty');
    expect(valueKind(DELETED)).toBe('deleted');
  });
});

describe('the rows of a change', () => {
  it('are Was and Now for a field the host has not changed', () => {
    expect(reviewRows({ kind: 'value', was: 'a', theirs: 'b' }, REVIEW_WORDS)).toEqual([
      { term: 'Was', text: 'a', kind: 'text' },
      { term: 'Now', text: 'b', kind: 'text' },
    ]);
  });

  it('add Yours, last, where the host changed it too', () => {
    const rows = reviewRows({ kind: 'value', was: 'a', theirs: 'b', mine: 'c' }, REVIEW_WORDS);

    expect(rows.map((row) => row.term)).toEqual(['Was', 'Now', 'Yours']);
    expect(rows[2]?.text).toBe('c');
  });

  it('keep an empty yours: the host changed it to nothing', () => {
    const rows = reviewRows({ kind: 'value', was: 'a', theirs: 'b', mine: EMPTY }, REVIEW_WORDS);

    expect(rows[2]).toEqual({ term: 'Yours', text: 'No value', kind: 'empty' });
  });

  it('say empty and deleted values in words, whichever side they are on', () => {
    const rows = reviewRows({ kind: 'value', was: EMPTY, theirs: DELETED }, REVIEW_WORDS);

    expect(rows).toEqual([
      { term: 'Was', text: 'No value', kind: 'empty' },
      { term: 'Now', text: 'Deleted', kind: 'deleted' },
    ]);
  });

  it('use the host words for the terms', () => {
    const words = reviewWords({ mine: 'Mine', theirs: 'Theirs' });
    const rows = reviewRows({ kind: 'value', was: 'a', theirs: 'b', mine: 'c' }, words);

    expect(rows.map((row) => row.term)).toEqual(['Was', 'Theirs', 'Mine']);
  });

  it('are Added and Removed for a set, leaving out a side with nothing', () => {
    expect(
      reviewRows({ kind: 'set', added: ['Weapon', 'Metal'], removed: ['Junk'] }, REVIEW_WORDS),
    ).toEqual([
      { term: 'Added', text: 'Weapon, Metal', kind: 'text' },
      { term: 'Removed', text: 'Junk', kind: 'text' },
    ]);
    expect(reviewRows({ kind: 'set', added: ['Weapon'], removed: [] }, REVIEW_WORDS)).toHaveLength(
      1,
    );
    expect(reviewRows({ kind: 'set', added: [], removed: [] }, REVIEW_WORDS)).toEqual([]);
  });
});
