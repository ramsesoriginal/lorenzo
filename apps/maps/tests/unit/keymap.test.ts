import { expect, test } from 'vitest';
import { createKeyMap, KEYMAP_STORAGE } from '../../src/lib/keymap';
import { TOOLS, toolById } from '../../src/lib/tools';

const memory = () => {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
};

const line = toolById('line');
const pin = toolById('pin');
if (!line || !pin) throw new Error('tools missing');

test('a tool keeps its declared key until a person chooses another', () => {
  const keys = createKeyMap(memory());
  expect(keys.keyOf(line)).toBe('l');
  expect(keys.set(line, 'Q')).toBeNull();
  expect(keys.keyOf(line)).toBe('q');
  expect(keys.toolFor('Q')?.id).toBe('line');
  expect(keys.toolFor('l')).toBeUndefined();
  expect(keys.isChanged(line)).toBe(true);
});

test('a taken key, the command line key and a non-letter are refused', () => {
  const keys = createKeyMap(memory());
  expect(keys.set(line, 'p')).toContain("Pin's key");
  expect(keys.set(line, '/')).toContain('command line');
  expect(keys.set(line, 'ab')).toContain('one letter');
  expect(keys.set(line, '!')).toContain('one letter');
  expect(keys.keyOf(line)).toBe('l');
});

test('the choice is kept in the storage, read back, and reset', () => {
  const store = memory();
  createKeyMap(store).set(pin, 'x');
  expect(store.getItem(KEYMAP_STORAGE)).toBe('{"pin":"x"}');
  const again = createKeyMap(store);
  expect(again.keyOf(pin)).toBe('x');
  again.reset();
  expect(store.getItem(KEYMAP_STORAGE)).toBeNull();
  expect(again.keyOf(pin)).toBe('p');
});

test('a spoiled or missing storage means the declared keys', () => {
  const store = memory();
  store.setItem(KEYMAP_STORAGE, 'not json');
  expect(createKeyMap(store).keyOf(pin)).toBe('p');
  expect(createKeyMap(null).keyOf(pin)).toBe('p');
  expect(TOOLS.length).toBeGreaterThan(0);
});
