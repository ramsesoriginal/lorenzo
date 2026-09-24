// Runs every example embedded in SPEC.md (ADR 0100): the spec is the test suite.
import { readFileSync } from 'node:fs';
import { describe, expect, test } from 'vitest';
import { parse, render } from '../src';

const FENCE = '`'.repeat(8);
type Example = { source: string; html: string };

/**
 * `␠` marks a trailing space and `⇥` a tab, so editors and hooks can't alter an example.
 * (Not `→`, as in CommonMark's spec: math renders `\to` as a real one.)
 */
const text = (lines: string[]) =>
  lines
    .map((l) => `${l}\n`)
    .join('')
    .replace(/␠/g, ' ')
    .replace(/⇥/g, '\t');

function sections(spec: string): Map<string, Example[]> {
  const out = new Map<string, Example[]>();
  let section = '';
  let parts: string[][] | null = null;
  for (const line of spec.replace(/\r\n/g, '\n').split('\n')) {
    if (parts && line === FENCE) {
      const [source = [], html = []] = parts;
      out.get(section)?.push({ source: text(source), html: text(html) });
      parts = null;
    } else if (parts) {
      if (line === '.') parts.push([]);
      else parts.at(-1)?.push(line);
    } else if (line === `${FENCE} example`) {
      parts = [[]];
    } else if (line.startsWith('## ')) {
      section = line.slice(3);
      out.set(section, []);
    }
  }
  return out;
}

const spec = readFileSync(new URL('../SPEC.md', import.meta.url), 'utf8');

for (const [section, examples] of sections(spec)) {
  if (!examples.length) continue;
  describe(section, () => {
    test.each(examples.map((ex, k) => ({ ...ex, name: `${k + 1}: ${ex.source.split('\n')[0]}` })))(
      '$name',
      ({ source, html }) => expect(render(parse(source))).toBe(html),
    );
  });
}

describe('outside SPEC.md', () => {
  test('externalImages: false renders images as their alt text', () => {
    const doc = parse('![A map](https://example.com/map.png)');
    expect(render(doc, { externalImages: false })).toBe('<p>A map</p>\n');
  });

  test('NUL becomes U+FFFD', () => {
    expect(render(parse('a\0b'))).toBe(`<p>a${String.fromCharCode(0xfffd)}b</p>\n`);
  });

  test('CRLF and CR line endings behave like LF', () => {
    expect(render(parse('a\r\nb\rc'))).toBe(render(parse('a\nb\nc')));
  });
});

// Descriptions are written by one user and rendered in another's browser, so no input
// may exhaust the stack or take super-linear time. These would throw or hang if it did.
describe('hostile input', () => {
  const count = (html: string, tag: string) => html.split(tag).length - 1;

  test('blocks nest at most MAX_NESTING deep; deeper markers are text', () => {
    const html = render(parse(`${'>'.repeat(5000)} a`));
    expect(count(html, '<blockquote>')).toBe(32);
    expect(html).toContain('&gt;&gt;&gt;');
  });

  test('inline spans nest at most MAX_NESTING deep; deeper delimiters are text', () => {
    const html = render(parse(`${'*'.repeat(5000)}a${'*'.repeat(5000)}`));
    expect(count(html, '<strong>') + count(html, '<em>')).toBe(32);
  });

  test('lazy lines in nested quotes stay linear', () => {
    const html = render(parse(`> > > > > a\n${'b\n'.repeat(2000)}`));
    expect(count(html, '<blockquote>')).toBe(5);
  });

  test('class blocks and spans nest at most MAX_NESTING deep', () => {
    const blocks = render(parse(`${'{{.a\n'.repeat(5000)}x\n${'}}\n'.repeat(5000)}`));
    const spans = render(parse(`${'{{.a '.repeat(5000)}x${'}}'.repeat(5000)}`));
    expect(count(blocks, '<div')).toBe(32);
    expect(count(spans, '<span')).toBe(32);
  });

  test('math nested past MAX_NESTING shows as code', () => {
    const html = render(parse(`$${'{'.repeat(5000)}x${'}'.repeat(5000)}$`));
    expect(html).toContain('<code class="ls-math">');
  });

  test('thousands of footnotes and equal headings stay linear', () => {
    const chain = Array.from({ length: 5000 }, (_, k) => `[^${k}]: see[^${k + 1}]`).join('\n');
    expect(count(render(parse(`${chain}\n\nstart[^0]`)), '<li id="ls-fn-')).toBe(5000);
    expect(render(parse('# a\n'.repeat(5000)))).toContain('id="ls-a-5000"');
  });
});
