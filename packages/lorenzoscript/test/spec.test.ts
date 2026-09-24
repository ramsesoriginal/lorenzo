// Runs every example embedded in SPEC.md (ADR 0100, 0105): the spec is the test suite.
import { readFileSync } from 'node:fs';
import { describe, expect, test } from 'vitest';
import { parse, type RenderOptions, references, render } from '../src';

const FENCE = '`'.repeat(8);
/** `refs`: the optional third section, the JSON `references()` must return. */
type Example = { source: string; html: string; refs?: string };

/** The fixture SPEC.md describes, which every example renders against. */
const ENTITIES: Record<string, { name: string; picture?: true }> = {
  ashfang: { name: 'Ashfang', picture: true },
  'old-sword': { name: 'Old Sword' },
};
const OPTIONS: RenderOptions = {
  locale: 'en-GB',
  resolve: {
    entity: ({ hint, slug }) => {
      const entity = ENTITIES[slug];
      return entity ? { href: `/${hint || 'entity'}/${slug}`, title: entity.name } : null;
    },
    image: ({ slug }) => {
      const entity = ENTITIES[slug];
      return entity?.picture ? { src: `/pictures/${slug}.png`, title: entity.name } : null;
    },
    calendar: (expression) =>
      expression === 'harptos 1492-mirtul-12' ? '12 Mirtul 1492 DR' : null,
  },
};

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
      const [source = [], html = [], refs] = parts;
      const example: Example = { source: text(source), html: text(html) };
      if (refs) example.refs = refs.join('\n');
      out.get(section)?.push(example);
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
      ({ source, html, refs }) => {
        const doc = parse(source);
        expect(render(doc, OPTIONS)).toBe(html);
        if (refs !== undefined) expect(references(doc)).toEqual(JSON.parse(refs));
      },
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

  test('without a resolver, entity references render as their text', () => {
    const doc = parse('[[Ashfang]], [the sword](ashfang) and ![Ashfang](ashfang)');
    expect(render(doc)).toBe('<p>Ashfang, the sword and Ashfang</p>\n');
  });

  test("a resolver's unsafe URL counts as unresolved", () => {
    const resolve = {
      entity: () => ({ href: 'javascript:alert(1)' }),
      image: () => ({ src: 'data:image/svg+xml,<svg onload=alert(1)>' }),
    };
    const doc = parse('[[Ashfang]] ![Ashfang](ashfang)');
    expect(render(doc, { resolve })).toBe('<p>Ashfang Ashfang</p>\n');
  });

  test('an unusable locale falls back to the runtime default', () => {
    expect(render(parse('{{date 2026-09-24}}'), { locale: 'not a locale!' })).toContain(
      '<time datetime="2026-09-24">',
    );
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
