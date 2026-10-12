import { describe, expect, it } from 'vitest';
import { effectiveMode, isMode, sectionOrder } from './sheetMode';

describe('effectiveMode', () => {
  it('keeps Edit for someone who may edit and falls back to Read for someone who may not', () => {
    expect(effectiveMode('edit', true)).toBe('edit');
    expect(effectiveMode('edit', false)).toBe('read');
  });

  it('never changes Read or Play', () => {
    expect(effectiveMode('read', false)).toBe('read');
    expect(effectiveMode('play', false)).toBe('play');
  });
});

describe('sectionOrder', () => {
  it('puts the numbers first in Play and the prose first otherwise', () => {
    expect(sectionOrder('play')).toEqual(['stats', 'inventory', 'notes', 'about']);
    expect(sectionOrder('read')).toEqual(['about', 'notes', 'stats', 'inventory']);
  });

  it('draws Edit in the same order as Read, so the page does not jump', () => {
    expect(sectionOrder('edit')).toEqual(sectionOrder('read'));
  });
});

describe('isMode', () => {
  it('knows the three modes and nothing else', () => {
    expect(['read', 'play', 'edit'].every(isMode)).toBe(true);
    expect(isMode('datasheet')).toBe(false);
    expect(isMode(null)).toBe(false);
  });
});
