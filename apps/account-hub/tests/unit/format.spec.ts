import { describe, expect, it } from 'vitest';
import { countUnread, localesToText, textOrNull, textToLocales } from '../../src/lib/format';
import type { Notification } from '../../src/lib/types';

function notification(read_at: string | null): Notification {
  return {
    id: crypto.randomUUID(),
    batch_id: crypto.randomUUID(),
    user_id: crypto.randomUUID(),
    scope: 'platform',
    type: 'test',
    tenant_id: null,
    source_id: null,
    title: 'Title',
    body: 'Body',
    read_at,
    created_at: new Date().toISOString(),
  };
}

describe('textToLocales', () => {
  it('splits, trims, and drops empty entries', () => {
    expect(textToLocales('en, de ,  , fr')).toEqual(['en', 'de', 'fr']);
  });

  it('returns an empty array for blank input', () => {
    expect(textToLocales('   ')).toEqual([]);
  });
});

describe('localesToText', () => {
  it('joins with a comma and space', () => {
    expect(localesToText(['en', 'de'])).toBe('en, de');
  });

  it('round-trips through textToLocales', () => {
    const locales = ['en', 'de', 'fr'];
    expect(textToLocales(localesToText(locales))).toEqual(locales);
  });
});

describe('textOrNull', () => {
  it('returns null for blank/whitespace-only input', () => {
    expect(textOrNull('')).toBeNull();
    expect(textOrNull('   ')).toBeNull();
  });

  it('returns the value unchanged otherwise', () => {
    expect(textOrNull('Cael')).toBe('Cael');
  });
});

describe('countUnread', () => {
  it('counts only notifications with a null read_at', () => {
    const items = [notification(null), notification('2026-01-01T00:00:00Z'), notification(null)];
    expect(countUnread(items)).toBe(2);
  });

  it('returns 0 for an empty list', () => {
    expect(countUnread([])).toBe(0);
  });

  it('returns 0 when everything is already read', () => {
    expect(countUnread([notification('2026-01-01T00:00:00Z')])).toBe(0);
  });
});
