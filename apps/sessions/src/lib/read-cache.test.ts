import { expect, test } from 'vitest';
import { readScope, sessionPolicy } from './read-cache';

const at = (path: string) => sessionPolicy(new URL(`https://api.example${path}`));

test('who the person is is kept across page loads', () => {
  for (const path of ['/me', '/tenants', '/app-links']) {
    expect(at(path)).toMatchObject({ persist: true, staleMs: 600_000 });
  }
});

test("the person's own lists and a library's reads are held in memory only", () => {
  for (const path of ['/me/sessions', '/me/managed', '/tenants/library/sessions/one']) {
    const held = at(path);

    expect(held).toEqual({ freshMs: 10_000 });
    expect(held?.persist).toBeUndefined();
  }
});

test('who may read something, lookups and anything else are never held', () => {
  expect(at('/tenants/library/entities/entry/access')).toBeNull();
  expect(at('/tenants/library/entities/resolve')).toBeNull();
  expect(at('/users/search')).toBeNull();
});

test('the scope is the viewer', () => {
  expect(readScope('a')).toBe(readScope('a'));
  expect(readScope('a')).not.toBe(readScope('b'));
});
