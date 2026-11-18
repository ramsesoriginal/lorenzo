// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it } from 'vitest';
import { createEditor } from '../src';

let textarea: HTMLTextAreaElement;
beforeEach(() => {
  document.body.innerHTML = '<textarea id="t"></textarea>';
  textarea = document.querySelector('#t') as HTMLTextAreaElement;
});
afterEach(() => {
  document.body.innerHTML = '';
});

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const blocks = () => [...document.querySelectorAll<HTMLElement>('.ls-block')];
const field = () => document.querySelector<HTMLTextAreaElement>('textarea.ls-semilive-field');
const key = (target: Element, k: string, more: KeyboardEventInit = {}) =>
  target.dispatchEvent(
    new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...more }),
  );

it('shows every block formatted and none as a text area until one is opened', async () => {
  textarea.value = '# Title\n\nSome *words*.\n\n- a\n- b';
  const editor = createEditor({ textarea });
  await flush();
  expect(blocks()).toHaveLength(3);
  expect(field()).toBeNull();
  expect(blocks()[0]?.querySelector('h1')?.textContent).toBe('Title');
  expect(blocks()[1]?.querySelector('em')?.textContent).toBe('words');
  expect(textarea.hidden).toBe(true);
  editor.destroy();
  expect(textarea.hidden).toBe(false);
  expect(document.querySelector('.ls-semilive')).toBeNull();
});

it('opens a block with Enter, edits its source, and keeps the whole text in the original', async () => {
  textarea.value = 'One.\n\nTwo.';
  createEditor({ textarea });
  await flush();
  key(blocks()[1] as HTMLElement, 'Enter');
  const open = field() as HTMLTextAreaElement;
  expect(open.value).toBe('Two.');
  open.value = 'Two, longer.';
  open.dispatchEvent(new Event('input', { bubbles: true }));
  expect(textarea.value).toBe('One.\n\nTwo, longer.');
});

it('moves between blocks with the arrows, at the edge of the text', async () => {
  textarea.value = 'One.\n\nTwo.';
  createEditor({ textarea });
  await flush();
  key(blocks()[0] as HTMLElement, 'Enter');
  const first = field() as HTMLTextAreaElement;
  first.setSelectionRange(first.value.length, first.value.length);
  key(first, 'ArrowDown');
  expect(field()?.value).toBe('Two.');
  const second = field() as HTMLTextAreaElement;
  second.setSelectionRange(0, 0);
  key(second, 'ArrowUp');
  expect(field()?.value).toBe('One.');
});

it('starts a new paragraph with Enter at the end, and a new line with Shift+Enter', async () => {
  textarea.value = 'One.';
  createEditor({ textarea });
  await flush();
  key(blocks()[0] as HTMLElement, 'Enter');
  const first = field() as HTMLTextAreaElement;
  first.setSelectionRange(4, 4);
  key(first, 'Enter', { shiftKey: true });
  expect(textarea.value).toBe('One.\n');
  (field() as HTMLTextAreaElement).setSelectionRange(5, 5);
  key(field() as HTMLTextAreaElement, 'Enter');
  expect(textarea.value).toBe('One.\n\n\n');
  const fresh = field() as HTMLTextAreaElement;
  expect(fresh.value).toBe('');
  fresh.value = 'Next.';
  fresh.dispatchEvent(new Event('input', { bubbles: true }));
  expect(textarea.value).toBe('One.\n\n\nNext.');
});

it('continues a list with Enter, the editor keys being the source editor’s', async () => {
  textarea.value = '- a';
  createEditor({ textarea });
  await flush();
  key(blocks()[0] as HTMLElement, 'Enter');
  const open = field() as HTMLTextAreaElement;
  open.setSelectionRange(3, 3);
  key(open, 'Enter');
  expect(textarea.value).toBe('- a\n- ');
});

it('undoes across paragraphs', async () => {
  textarea.value = 'One.\n\nTwo.';
  createEditor({ textarea });
  await flush();
  key(blocks()[0] as HTMLElement, 'Enter');
  const open = field() as HTMLTextAreaElement;
  open.value = 'One, changed.';
  open.dispatchEvent(new Event('input', { bubbles: true }));
  key(open, 'ArrowDown');
  key(open, 'z', { ctrlKey: true });
  expect(textarea.value).toBe('One.\n\nTwo.');
});

it('opens an empty text as one block to type into', async () => {
  createEditor({ textarea });
  await flush();
  expect(field()).not.toBeNull();
});
