import { describe, expect, it, vi } from 'vitest';
import { isLayout, isMode, rememberMode, savedMode, sectionOrder } from './sheetMode';

describe('the mode remembered for a being', () => {
  it('is Read until Play was last used, and is kept per being', () => {
    const store = new Map<string, string>();

    vi.stubGlobal('window', {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => void store.set(key, value),
      },
    });
    expect(savedMode('t', 'a')).toBe('read');
    rememberMode('t', 'a', 'play');
    expect(savedMode('t', 'a')).toBe('play');
    expect(savedMode('t', 'b')).toBe('read');
    rememberMode('t', 'a', 'read');
    expect(savedMode('t', 'a')).toBe('read');
    vi.unstubAllGlobals();
  });

  it('is Read where storage is not available', () => {
    vi.stubGlobal('window', {
      localStorage: {
        getItem: () => {
          throw new Error('blocked');
        },
      },
    });
    expect(savedMode('t', 'a')).toBe('read');
    vi.unstubAllGlobals();
  });
});

describe('sectionOrder', () => {
  it('puts the numbers first in Play and the prose first otherwise', () => {
    expect(sectionOrder('play')).toEqual(['stats', 'inventory', 'notes', 'about']);
    expect(sectionOrder('read')).toEqual(['about', 'notes', 'stats', 'inventory']);
  });
});

describe('isMode', () => {
  it('knows the two modes and nothing else', () => {
    expect(['read', 'play'].every(isMode)).toBe(true);
    expect(isMode('edit')).toBe(false);
    expect(isMode('datasheet')).toBe(false);
    expect(isMode(null)).toBe(false);
  });
});

describe('isLayout', () => {
  it('knows the two layouts and nothing else', () => {
    expect(isLayout('sheet') && isLayout('datasheet')).toBe(true);
    expect(isLayout('play')).toBe(false);
  });
});
