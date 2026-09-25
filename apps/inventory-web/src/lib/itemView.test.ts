import { describe, expect, it, vi } from 'vitest';

vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));
vi.mock('./me', () => ({ viewerLocales: async () => ['en-GB'] }));

import { statLabel } from './itemView';
import { tagState } from './tagEditor';

describe('statLabel', () => {
  it('reads a stat or tag name as a label', () => {
    expect(statLabel('is_magical')).toBe('Magical');
    expect(statLabel('weight')).toBe('Weight');
    expect(statLabel('max_hp')).toBe('Max HP');
    expect(statLabel('hp')).toBe('HP');
  });
});

describe('tagState', () => {
  const stat = (value: boolean, own: boolean) => ({ name: 'is_magical', value, own });

  it('is On or Off when the entity sets the tag itself', () => {
    expect(tagState(stat(true, true))).toEqual({ state: 'on', hint: '' });
    expect(tagState(stat(false, true))).toEqual({ state: 'off', hint: '' });
  });

  it('is Inherited otherwise, saying what inheriting gives', () => {
    expect(tagState(stat(true, false))).toEqual({ state: 'inherited', hint: ' (on)' });
    expect(tagState(stat(false, false))).toEqual({ state: 'inherited', hint: ' (off)' });
    expect(tagState(undefined)).toEqual({ state: 'inherited', hint: ' (not set)' });
  });
});
