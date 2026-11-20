import { strToU8, zipSync } from 'fflate';
import { describe, expect, it } from 'vitest';
import { toDocx } from './docx-export';
import { fromDocx } from './docx-import';
import type { Part } from './export-parts';
import { parseXml } from './xml';

const PNG =
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAYAAAD0In+KAAAAD0lEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==';

describe('the XML reader', () => {
  it('reads elements, attributes, entities and CDATA', () => {
    const root = parseXml(
      '<?xml version="1.0"?><a x="1 &amp; 2" y=\'q\'><!-- c --><b/><c>t &lt;u&gt; &#65;<![CDATA[<raw>]]></c></a>',
    );
    expect(root.name).toBe('a');
    expect(root.attrs).toEqual({ x: '1 & 2', y: 'q' });
    const c = root.children.find((child) => typeof child !== 'string' && child.name === 'c');
    expect(typeof c === 'object' && c.children.join('')).toBe('t <u> A<raw>');
  });

  it('refuses a text with no element', () => {
    expect(() => parseXml('just words')).toThrow(/no document/);
  });
});

describe('Word in, from what this app writes', () => {
  const parts: Part[] = [
    { kind: 'heading', depth: 1, text: 'The crossing' },
    {
      kind: 'text',
      content:
        'The **river**[^a] *remembers* a [bank](https://example.com/a?x=1&y=2) and [[Ash]].\n\n' +
        '> A quoted line.\n\n- one\n- two\n\n1. first\n2. second\n\n```\ncode line\n  indented\n```\n\n' +
        '| A | B |\n|---|---|\n| 1 | 2 |\n\n[^a]: A footnote.',
    },
    { kind: 'heading', depth: 2, text: 'Arrival' },
    { kind: 'text', content: 'Second text with a_b and 2 * 3.' },
    { kind: 'picture', mediaType: 'image/png', data: PNG },
  ];
  const result = fromDocx('crossing.docx', toDocx(parts));

  it('takes the first heading as the title and keeps the others', () => {
    expect(result.title).toBe('The crossing');
    expect(result.content).toContain('## Arrival');
    expect(result.content).not.toMatch(/^# The crossing/);
  });

  it('keeps bold, italic, links and [[links]]', () => {
    expect(result.content).toContain('**river**');
    expect(result.content).toContain('*remembers*');
    expect(result.content).toContain('[bank](https://example.com/a?x=1&y=2)');
  });

  it('keeps lists, quotes, code and tables', () => {
    expect(result.content).toContain('- one\n- two');
    expect(result.content).toContain('1. first\n1. second');
    expect(result.content).toContain('> A quoted line.');
    expect(result.content).toContain('```\ncode line\n  indented\n```');
    expect(result.content).toContain('| **A** | **B** |\n| --- | --- |\n| 1 | 2 |');
  });

  it('keeps footnotes and makes plain text plain', () => {
    expect(result.content).toContain('[^1]');
    expect(result.content).toContain('[^1]: A footnote.');
    expect(result.content).toContain('a\\_b and 2 \\* 3.');
  });

  it('says what it left out', () => {
    expect(result.notes).toEqual(['1 picture was not imported']);
  });
});

describe('Word in, from a file made by Word', () => {
  const W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';
  const file = (document: string, extra: Record<string, string> = {}) =>
    zipSync({
      'word/document.xml': strToU8(`<w:document ${W}><w:body>${document}</w:body></w:document>`),
      'word/styles.xml': strToU8(
        `<w:styles ${W}><w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style><w:style w:styleId="Heading2"><w:name w:val="heading 2"/></w:style></w:styles>`,
      ),
      'word/numbering.xml': strToU8(
        `<w:numbering ${W}><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum><w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>`,
      ),
      ...Object.fromEntries(Object.entries(extra).map(([k, v]) => [k, strToU8(v)])),
    });

  it('reads Word headings by their style names, and runs split across Word edits', () => {
    const doc = file(
      `<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>My </w:t></w:r><w:r><w:t>Title</w:t></w:r></w:p>` +
        `<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Part</w:t></w:r></w:p>` +
        `<w:p><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Bold </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>words</w:t></w:r><w:r><w:t xml:space="preserve"> and plain.</w:t></w:r></w:p>` +
        `<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>counted</w:t></w:r></w:p>` +
        `<w:p><w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t>nested bullet</w:t></w:r></w:p>`,
    );
    const result = fromDocx('my.docx', doc);
    expect(result.title).toBe('My Title');
    expect(result.content).toBe(
      '## Part\n\n**Bold words** and plain.\n\n1. counted\n  - nested bullet',
    );
  });

  it('reads a hyperlink through its relationship and ignores deleted text', () => {
    const doc = file(
      `<w:p><w:hyperlink r:id="rId9" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:r><w:t>site</w:t></w:r></w:hyperlink><w:del><w:r><w:delText>gone</w:delText></w:r></w:del></w:p>`,
      {
        'word/_rels/document.xml.rels':
          '<Relationships><Relationship Id="rId9" Type="http://x/hyperlink" Target="https://example.com/"/></Relationships>',
      },
    );
    expect(fromDocx('l.docx', doc).content).toBe('[site](https://example.com/)');
  });

  it('keeps [[links]] typed in Word, for the link review', () => {
    const doc = file(
      '<w:p><w:r><w:t>Met [[Ash]] and [[The Ferry|ferry]] on the *road* [x].</w:t></w:r></w:p>',
    );
    expect(fromDocx('k.docx', doc).content).toBe(
      'Met [[Ash]] and [[The Ferry|ferry]] on the \\*road\\* \\[x\\].',
    );
  });

  it('refuses what is not a Word file', () => {
    expect(() => fromDocx('x.docx', strToU8('plain text'))).toThrow(/not a Word/);
    expect(() => fromDocx('x.docx', zipSync({ 'a.txt': strToU8('a') }))).toThrow(/not a Word/);
  });
});
