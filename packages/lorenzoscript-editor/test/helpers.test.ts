// @vitest-environment jsdom
import { expect, test } from 'vitest';
import { createEditor } from '../src';

const paste = (textarea: HTMLTextAreaElement, html: string, text = '') => {
  const event = new Event('paste', { bubbles: true, cancelable: true });
  Object.defineProperty(event, 'clipboardData', {
    value: { getData: (type: string) => (type === 'text/html' ? html : text) },
  });
  textarea.dispatchEvent(event);
  return event;
};

test('pasting HTML becomes LorenzoScript only when asked for', () => {
  document.body.innerHTML = '<textarea id="a"></textarea><textarea id="b"></textarea>';
  const a = document.querySelector('#a') as HTMLTextAreaElement;
  const b = document.querySelector('#b') as HTMLTextAreaElement;
  createEditor({ textarea: a, pasteFromWord: true });
  createEditor({ textarea: b });
  expect(paste(a, '<p>Some <b>bold</b> words</p>').defaultPrevented).toBe(true);
  expect(a.value).toBe('Some **bold** words');
  expect(paste(b, '<p>Some <b>bold</b> words</p>').defaultPrevented).toBe(false);
  expect(b.value).toBe('');
});

test('find and replace opens with Ctrl+H and replaces all', () => {
  document.body.innerHTML = '<textarea id="t">ash and ash</textarea>';
  const t = document.querySelector('#t') as HTMLTextAreaElement;
  createEditor({ textarea: t, findReplace: true });
  const bar = document.querySelector<HTMLElement>('.ls-find') as HTMLElement;
  expect(bar.hidden).toBe(true);
  t.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'h', ctrlKey: true, bubbles: true, cancelable: true }),
  );
  expect(bar.hidden).toBe(false);
  const [find, replace] = bar.querySelectorAll('input');
  (find as HTMLInputElement).value = 'ash';
  find?.dispatchEvent(new Event('input'));
  expect(bar.querySelector('[role=status]')?.textContent).toBe('2 matches');
  (replace as HTMLInputElement).value = 'ember';
  [...bar.querySelectorAll('button')].find((b) => b.textContent === 'Replace all')?.click();
  expect(t.value).toBe('ember and ember');
});
