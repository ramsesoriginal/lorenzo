import { describe, expect, it } from 'vitest';
import type { EntrySummary } from '../core/transport';
import { applyPick, choices, linkFor, pickerContext } from './entryPickerText';

const e = (id: string, name: string): EntrySummary => ({ id, name, kinds: [], parentIds: [] });

describe('where the person is in a link', () => {
  it('finds an open [[ before the caret and what follows it', () => {
    expect(pickerContext('See [[Old Sw', 12)).toEqual({ start: 4, query: 'Old Sw' });
    expect(pickerContext('See [[', 6)).toEqual({ start: 4, query: '' });
  });

  it('is not in a link when none is open, it is closed, or it is on another line', () => {
    expect(pickerContext('plain text', 5)).toBeNull();
    expect(pickerContext('See [[Old Sword]] and', 21)).toBeNull();
    expect(pickerContext('See [[Old\nSword', 15)).toBeNull();
  });

  it('uses the last [[ before the caret', () => {
    expect(pickerContext('[[A]] and [[Bo', 14)).toEqual({ start: 10, query: 'Bo' });
  });
});

describe('choosing an entry', () => {
  it('writes the whole link, caret after it', () => {
    const text = 'See [[Old Sw and more';
    const ctx = pickerContext(text, 12);
    expect(ctx).not.toBeNull();
    expect(applyPick(text, 12, ctx as never, '[[Old Sword]]')).toEqual({
      text: 'See [[Old Sword]] and more',
      caret: 17,
    });
  });

  it('takes a ]] already after the caret as its own', () => {
    const text = 'See [[Old Sw]] and';
    const ctx = pickerContext(text, 12);
    expect(applyPick(text, 12, ctx as never, '[[Old Sword]]').text).toBe('See [[Old Sword]] and');
  });
});

describe('what to offer', () => {
  const all = [
    e('1', 'Wolf'),
    e('2', 'Dire wolf'),
    e('3', 'Ashfang'),
    e('4', 'Old [odd] name'),
    e('5', '日本'),
  ];

  it('offers entries that start with what was typed before those that contain it', () => {
    expect(choices(all, 'wol').map((x) => x.name)).toEqual(['Wolf', 'Dire wolf']);
  });

  it('offers by name when nothing is typed, and leaves out names that cannot be linked', () => {
    const names = choices(all, '').map((x) => x.name);
    expect(names).toEqual(['Ashfang', 'Dire wolf', 'Wolf']);
  });

  it('offers nothing for what no name has, and at most eight', () => {
    expect(choices(all, 'zzz')).toEqual([]);
    const many = Array.from({ length: 20 }, (_, i) => e(String(i), `Entry ${i}`));
    expect(choices(many, 'entry')).toHaveLength(8);
  });
});

describe('the link written for an entry', () => {
  it('is [[Name]] when its link name is the one its name makes', () => {
    expect(linkFor('Old Sword', 'old-sword')).toBe('[[Old Sword]]');
  });

  it('is [Name](link-name) when it has another', () => {
    expect(linkFor('Old Sword', 'blade')).toBe('[Old Sword](blade)');
  });

  it('is [[Name]] when it has none, which the preview says does not reach it', () => {
    expect(linkFor('Old Sword', null)).toBe('[[Old Sword]]');
  });
});
