import { describe, expect, it } from 'vitest';
import type { Part } from './export-parts';
import { countLinks, fileStem, fromMarkdown, toMarkdown } from './markdown';

describe('Markdown out', () => {
  const parts: Part[] = [
    { kind: 'heading', depth: 1, text: 'I The crossing' },
    { kind: 'text', content: 'The river[^a] remembers.\n\n[^a]: A note.' },
    { kind: 'heading', depth: 2, text: 'Arrival' },
    { kind: 'text', content: 'Second[^a] text.\n\n[^a]: Another note.' },
    { kind: 'picture', mediaType: 'image/png', data: 'AAAA' },
  ];

  it('writes headings, source and pictures in order', () => {
    const md = toMarkdown(parts);
    expect(md.startsWith('# I The crossing\n\n')).toBe(true);
    expect(md).toContain('## Arrival');
    expect(md).toContain('![Manuscript illustration](data:image/png;base64,AAAA)');
    expect(md.endsWith('\n')).toBe(true);
  });

  it('keeps the footnotes of different texts apart', () => {
    const md = toMarkdown(parts);
    expect(md).toContain('[^t1-a]');
    expect(md).toContain('[^t2-a]');
    expect(md).not.toContain('[^a]');
  });

  it('leaves a single text as it is', () => {
    expect(toMarkdown([{ kind: 'text', content: 'One[^x].\n\n[^x]: n' }])).toContain('[^x]');
  });
});

describe('file names', () => {
  it('makes a plain stem', () => {
    expect(fileStem('The Long Water: part 1')).toBe('The-Long-Water-part-1');
    expect(fileStem('???')).toBe('manuscript');
  });
});

describe('Markdown in', () => {
  it('takes the first heading as the title', () => {
    expect(fromMarkdown('x.md', '# Dawn\n\nThe first words.\n')).toEqual({
      title: 'Dawn',
      content: 'The first words.',
    });
  });

  it('falls back to the file name', () => {
    expect(fromMarkdown('the-long_water.md', 'Just text.')).toEqual({
      title: 'the long water',
      content: 'Just text.',
    });
  });

  it('reads and drops front matter, and keeps the title it names', () => {
    const doc = fromMarkdown('n.md', '---\ntitle: "Ferry log"\ntags: [a]\n---\n\nBody [[Ash]].');
    expect(doc).toEqual({ title: 'Ferry log', content: 'Body [[Ash]].' });
  });

  it('handles Windows line ends and a byte order mark', () => {
    expect(fromMarkdown('n.md', '﻿# T\r\n\r\nA\r\nB')).toEqual({ title: 'T', content: 'A\nB' });
  });

  it('counts the links to review', () => {
    expect(countLinks('See [[Ash]] and [[The Ferry]], not [x] or [[ ]')).toBe(2);
  });
});
