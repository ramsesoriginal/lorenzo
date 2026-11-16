import { describe, expect, it } from 'vitest';
import { fieldPatch, typedValue } from '../../src/lib/profileFields';
import type { MeOut } from '../../src/lib/types';

const me = {
  nickname: 'mara',
  display_name: null,
  pronouns: 'she/her',
  bio: null,
  locales: ['en', 'de'],
  user_color: '#B5471E',
} as unknown as MeOut;

describe('typedValue', () => {
  it('reads each field as it would be typed', () => {
    expect(typedValue(me, 'nickname')).toBe('mara');
    expect(typedValue(me, 'display_name')).toBe('');
    expect(typedValue(me, 'locales')).toBe('en, de');
    expect(typedValue(me, 'user_color')).toBe('#B5471E');
  });
});

describe('fieldPatch', () => {
  it('is null when the field holds what was typed', () => {
    expect(fieldPatch(me, 'nickname', 'mara')).toBeNull();
    expect(fieldPatch(me, 'display_name', '   ')).toBeNull();
    expect(fieldPatch(me, 'locales', 'de, en, de')).not.toBeNull();
    expect(fieldPatch(me, 'locales', 'en,de')).toBeNull();
  });

  it('is the one field that changed', () => {
    expect(fieldPatch(me, 'display_name', 'Mara Quill')).toEqual({ display_name: 'Mara Quill' });
    expect(fieldPatch(me, 'locales', 'en-GB')).toEqual({ locales: ['en-GB'] });
  });

  it('sends null to clear a field', () => {
    expect(fieldPatch(me, 'pronouns', '')).toEqual({ pronouns: null });
    expect(fieldPatch(me, 'user_color', '')).toEqual({ user_color: null });
  });
});
