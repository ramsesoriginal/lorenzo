// @vitest-environment jsdom
import { expect, test } from 'vitest';
import { htmlToScript, worthConverting } from '../src/paste';

test('headings, emphasis, links and lists survive; Word’s styles do not', () => {
  const html = `<html><head><style>p.MsoNormal{margin:0}</style></head><body>
    <h2 class="MsoHeading">The crossing</h2>
    <p class="MsoNormal" style="margin:0">She was <b>very</b> <i>quiet</i> and read <a href="https://example.org/x">this</a>.<o:p></o:p></p>
    <ul><li>a lantern</li><li>a <strong>rope</strong></li></ul>
    <ol><li>first</li><li>second</li></ol>
    <blockquote><p>The water remembers.</p></blockquote></body></html>`;
  expect(htmlToScript(html)).toBe(
    [
      '## The crossing',
      '',
      'She was **very** *quiet* and read [this](https://example.org/x).',
      '',
      '- a lantern',
      '- a **rope**',
      '',
      '1. first',
      '2. second',
      '',
      '> The water remembers.',
    ].join('\n'),
  );
});

test('Google Docs says bold and italic in a span’s style', () => {
  expect(
    htmlToScript(
      '<p><span style="font-weight:700">bold</span> and <span style="font-style:italic">slanted</span></p>',
    ),
  ).toBe('**bold** and *slanted*');
});

test('unsafe link targets lose the link, and plain text is not worth converting', () => {
  expect(htmlToScript('<p><a href="javascript:alert(1)">click</a></p>')).toBe('click');
  expect(worthConverting('<p>just words</p>')).toBe(false);
  expect(worthConverting('<p><b>words</b></p>')).toBe(true);
});

test('entities decode, code is kept, scripts and comments are dropped, broken HTML does not throw', () => {
  expect(htmlToScript('<p>a &amp; b &lt;c&gt; &#8212; &nbsp;<code>x &lt; y</code></p>')).toBe(
    'a & b <c> — `x < y`',
  );
  expect(htmlToScript('<p>hi<script>alert(1)</script><!-- note --> there</p>')).toBe('hi there');
  expect(htmlToScript('<p>open <b>bold <i>both</p> after')).toBe('open **bold *both***\n\nafter');
  expect(htmlToScript('<p>cut <a href="https://e.org')).toBe('cut');
  expect(htmlToScript('<!-- <!-- <!-- '.repeat(5000))).toBe('');
});
