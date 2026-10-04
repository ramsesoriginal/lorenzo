import { describe, expect, it } from 'vitest';
import {
  RETURN_PATH_KEY,
  rememberReturnPath,
  safeReturnPath,
  takeReturnPath,
} from '../../src/lib/returnPath';

function fakeStorage(initial: Record<string, string> = {}) {
  const items = new Map(Object.entries(initial));
  return {
    items,
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
    removeItem: (key: string) => void items.delete(key),
  };
}

describe('safeReturnPath', () => {
  it.each([
    ['/profile', '/profile'],
    ['/tenants?tenant=north', '/tenants?tenant=north'],
    ['/join/', '/join/'],
    ['/', '/'],
  ])('keeps a path on this origin: %s', (value, expected) => {
    expect(safeReturnPath(value)).toBe(expected);
  });

  it('drops a fragment: nothing after the # is a destination, and a token may be there', () => {
    expect(safeReturnPath('/join/#a-token')).toBe('/join/');
  });

  it.each([
    ['//evil.example/path'],
    ['https://evil.example/'],
    ['/\\evil.example'],
    ['javascript:alert(1)'],
    ['profile'],
    [''],
    ['/auth/redirect/'],
    ['/auth/redirect?code=1'],
    [`/${'a'.repeat(600)}`],
    [null],
    [undefined],
    [42],
  ])('sends anything else home: %s', (value) => {
    expect(safeReturnPath(value)).toBe('/');
  });
});

describe('remembering and taking a return path', () => {
  it('round-trips a path and forgets it once taken', () => {
    const storage = fakeStorage();
    rememberReturnPath(storage, '/characters?x=1');
    expect(storage.items.get(RETURN_PATH_KEY)).toBe('/characters?x=1');
    expect(takeReturnPath(storage)).toBe('/characters?x=1');
    expect(storage.items.has(RETURN_PATH_KEY)).toBe(false);
    expect(takeReturnPath(storage)).toBe('/');
  });

  it('never stores what it would not return', () => {
    const storage = fakeStorage();
    rememberReturnPath(storage, '//evil.example');
    expect(storage.items.get(RETURN_PATH_KEY)).toBe('/');
  });

  it('does not trust what is already in storage', () => {
    const storage = fakeStorage({ [RETURN_PATH_KEY]: 'https://evil.example/' });
    expect(takeReturnPath(storage)).toBe('/');
  });

  it('copes with no storage, or storage that throws', () => {
    const broken = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
      removeItem: () => {
        throw new Error('blocked');
      },
    };
    expect(() => rememberReturnPath(undefined, '/profile')).not.toThrow();
    expect(() => rememberReturnPath(broken, '/profile')).not.toThrow();
    expect(takeReturnPath(undefined)).toBe('/');
    expect(takeReturnPath(broken)).toBe('/');
  });
});
