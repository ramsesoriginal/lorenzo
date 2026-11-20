import { writeFileSync } from 'node:fs';
import { strFromU8, unzipSync } from 'fflate';
import { describe, expect, it } from 'vitest';
import { imageSize, toDocx } from './docx-export';
import type { Part } from './export-parts';

// A 2 x 1 pixel PNG.
const PNG =
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAYAAAD0In+KAAAAD0lEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==';

const text = (content: string): Part => ({ kind: 'text', content });
const SAMPLE: Part[] = [
  { kind: 'heading', depth: 1, text: 'I The crossing' },
  text(
    'The **river**[^a] *remembers* a [bank](https://example.com/a?x=1&y=2) and [[Ash]].\n\n' +
      '> A quoted line.\n\n- one\n- two\n\n1. first\n2. second\n\n```\ncode line\n  indented\n```\n\n' +
      '| A | B |\n|---|---|\n| 1 | 2 |\n\n---\n\n[^a]: A footnote & its <note>.',
  ),
  { kind: 'heading', depth: 2, text: 'Arrival' },
  text('## Inside heading\n\nSecond text.'),
  { kind: 'picture', mediaType: 'image/png', data: PNG },
];

function read(parts: Part[]) {
  const files = unzipSync(toDocx(parts));
  const get = (name: string) => strFromU8(files[name] ?? new Uint8Array());
  return { files, get, document: get('word/document.xml') };
}

describe('Word out', () => {
  it('writes the parts a Word file needs', () => {
    const { files } = read(SAMPLE);
    for (const name of [
      '[Content_Types].xml',
      '_rels/.rels',
      'word/document.xml',
      'word/styles.xml',
      'word/footnotes.xml',
      'word/numbering.xml',
      'word/_rels/document.xml.rels',
      'word/media/image1.png',
    ])
      expect(files[name], name).toBeDefined();
  });

  it('turns the outline and the text into Word styles and runs', () => {
    const { document } = read(SAMPLE);
    expect(document).toContain('<w:pStyle w:val="Heading1"/>');
    expect(document).toContain('<w:pStyle w:val="Heading2"/>');
    // A heading inside a text sits below the heading of its Chapter.
    expect(document).toMatch(/Inside heading/);
    expect(document).toContain('<w:b/>');
    expect(document).toContain('<w:i/>');
    expect(document).toContain('<w:tbl>');
    expect(document).toContain('<w:numPr>');
    expect(document).toContain('<w:pStyle w:val="Quote"/>');
    expect(document).toContain('<w:pStyle w:val="Code"/>');
  });

  it('makes links, footnotes and pictures real', () => {
    const { document, get } = read(SAMPLE);
    expect(document).toContain('<w:hyperlink r:id="rIdLink1">');
    expect(get('word/_rels/document.xml.rels')).toContain(
      'Target="https://example.com/a?x=1&amp;y=2"',
    );
    expect(document).toContain('<w:footnoteReference w:id="2"/>');
    expect(get('word/footnotes.xml')).toContain('A footnote &amp; its &lt;note&gt;.');
    expect(document).toContain('r:embed="rIdImage1"');
  });

  it('keeps the library links as words, with no address', () => {
    const { get } = read(SAMPLE);
    expect(get('word/_rels/document.xml.rels')).not.toContain('Ash');
  });

  it('escapes what XML cannot hold', () => {
    const { document } = read([text('a < b & c \u0001 d')]);
    expect(document).toContain('a &lt; b &amp; c  d');
  });

  it('reads the size of a picture', () => {
    expect(imageSize(Uint8Array.from(atob(PNG), (c) => c.charCodeAt(0)))).toEqual({
      width: 2,
      height: 1,
    });
  });

  it('writes a file for other tools to check when asked', () => {
    if (process.env.DOCX_OUT) writeFileSync(process.env.DOCX_OUT, toDocx(SAMPLE));
    expect(true).toBe(true);
  });
});
