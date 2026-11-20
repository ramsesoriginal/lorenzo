import { expect, test } from 'vitest';
import { highlightSource } from '../src/highlight';

const plain = (html: string) =>
  html
    .replaceAll('</span>', '')
    .replace(/<span class="ls-hl-[a-z]+">/g, '')
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
    .replaceAll('&amp;', '&');

test('wraps only the markers, and the text stays the same characters', () => {
  const source =
    '# Title\n\nSome **bold** and *slanted* with `code`, [[Ash]] and [a](http://x).\n\n- item\n> quote';
  const html = highlightSource(source);
  expect(plain(html)).toBe(source);
  expect(html).toContain('<span class="ls-hl-mark">#</span>');
  expect(html).toContain('<span class="ls-hl-code">`code`</span>');
  expect(html).toContain('<span class="ls-hl-ref">[[Ash]]</span>');
  expect(html).toContain('<span class="ls-hl-link">[a](http://x)</span>');
  expect(html).toContain('<span class="ls-hl-mark">- </span>');
});

test('escapes markup in the text, and holds a code fence together', () => {
  const html = highlightSource('<script>alert(1)</script> & <b>\n```\n# not a heading\n```');
  expect(html).not.toContain('<script>');
  expect(html).toContain('&lt;script&gt;');
  expect(html).toContain('<span class="ls-hl-code"># not a heading</span>');
  expect(plain(html)).toBe('<script>alert(1)</script> & <b>\n```\n# not a heading\n```');
});

test('a long run of markers is read in one pass', () => {
  const line = '*'.repeat(50000);
  const start = Date.now();
  highlightSource(line);
  expect(Date.now() - start).toBeLessThan(1000);
});
