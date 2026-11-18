import { expect, test } from 'vitest';
import { type KeyInput, keyAction } from '../src';

const key = (k: string, more: Partial<KeyInput> = {}): KeyInput => ({
  key: k,
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  shiftKey: false,
  ...more,
});

test('Tab indents, unless the key before was Escape', () => {
  const state = { text: '- a', start: 3, end: 3 };
  expect(keyAction(key('Tab'), state).handled).toBe(true);
  expect(keyAction(key('Tab'), state, true).handled).toBe(false);
});

test('Enter continues a list, and leaves ordinary text to the browser', () => {
  const list = keyAction(key('Enter'), { text: '- a', start: 3, end: 3 });
  expect(list).toEqual({ handled: true, state: { text: '- a\n- ', start: 6, end: 6 } });
  expect(keyAction(key('Enter'), { text: 'plain', start: 5, end: 5 }).handled).toBe(false);
  expect(
    keyAction(key('Enter', { shiftKey: true }), { text: '- a', start: 3, end: 3 }).handled,
  ).toBe(false);
});

test('Ctrl or Cmd with a shortcut key runs its action', () => {
  const result = keyAction(key('b', { ctrlKey: true }), { text: 'word', start: 0, end: 4 });
  expect(result).toEqual({ handled: true, state: { text: '**word**', start: 2, end: 6 } });
  expect(keyAction(key('b'), { text: 'word', start: 0, end: 4 }).handled).toBe(false);
});
