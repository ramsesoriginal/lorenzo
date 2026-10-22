import { expect, test } from 'vitest';
import { calendarPolicy, isPureWrite, readScope } from './read-cache';

const at = (path: string) => calendarPolicy(new URL(`https://api.example${path}`));

test('who the person is is kept across page loads, and answered at once when stale', () => {
  for (const path of ['/me', '/tenants', '/app-links']) {
    expect(at(path)).toMatchObject({ persist: true, staleMs: 600_000 });
  }
});

test('a library is held in memory only, for a short time', () => {
  const held = at('/tenants/library/entities/entry');

  expect(held).toEqual({ freshMs: 10_000 });
  expect(held?.persist).toBeUndefined();
});

test('access, lookups and anything outside a library are never held', () => {
  expect(at('/tenants/library/events/access')).toBeNull();
  expect(at('/tenants/library/entities/resolve')).toBeNull();
  expect(at('/tenants/library/entities/by-slug/harbour')).toBeNull();
  expect(at('/users/search')).toBeNull();
});

test('a preview or comparison does not empty the cache, any other write does', () => {
  const url = (path: string) => new URL(`https://api.example${path}`);

  expect(isPureWrite(url('/tenants/a/calendars/preview'))).toBe(true);
  expect(isPureWrite(url('/tenants/a/events/compare'))).toBe(true);
  expect(isPureWrite(url('/tenants/a/calendar-references/resolve'))).toBe(true);
  expect(isPureWrite(url('/tenants/a/entities/1/information'))).toBe(false);
});

test('the scope changes with the viewer, the library, the role and what they may do', () => {
  const access = { canOrder: false, canReadOrder: true, canRetainPrivate: false };
  const base = readScope('a', 'library', 'player', access);

  expect(readScope('a', 'library', 'player', access)).toBe(base);
  expect(readScope('b', 'library', 'player', access)).not.toBe(base);
  expect(readScope('a', 'other', 'player', access)).not.toBe(base);
  expect(readScope('a', 'library', 'owner', access)).not.toBe(base);
  expect(readScope('a', 'library', 'player', { ...access, canOrder: true })).not.toBe(base);
});
