// Markdown out and in (ADR 0521). LorenzoScript is a Markdown dialect, so the source goes out as it
// is, with the headings of the outline in front of each part, and a Markdown file comes in as the
// text of a Chapter.
import type { Part } from './export-parts';

/** A footnote label is local to its text; in one file it must not meet another text's. */
function scopeFootnotes(content: string, scope: number): string {
  return content.replace(/\[\^([^\]\s]+)\]/g, (_, label: string) => `[^t${scope}-${label}]`);
}

/** The parts as one Markdown file: headings as #, texts as their source, pictures as data images. */
export function toMarkdown(parts: Part[]): string {
  const texts = parts.filter((part) => part.kind === 'text').length;
  let scope = 0;
  const blocks = parts.map((part) => {
    if (part.kind === 'heading') return `${'#'.repeat(part.depth)} ${part.text}`;
    if (part.kind === 'picture')
      return `![Manuscript illustration](data:${part.mediaType};base64,${part.data})`;
    scope += 1;
    const content = part.content.replace(/\r\n?/g, '\n').trim();
    return texts > 1 ? scopeFootnotes(content, scope) : content;
  });
  return `${blocks.filter((block) => block.length > 0).join('\n\n')}\n`;
}

/** A name safe to use as a file name: words and dashes, never empty. */
export function fileStem(name: string): string {
  const stem = name
    .normalize('NFKD')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
  return stem || 'manuscript';
}

export type Imported = { title: string; content: string };

/** What a Markdown file says it is called, and the text without that heading and front matter. */
export function fromMarkdown(fileName: string, text: string): Imported {
  let body = text.replace(/^﻿/, '').replace(/\r\n?/g, '\n');
  let title = '';
  const front = /^---\n([\s\S]*?)\n---\n?/.exec(body);
  if (front) {
    body = body.slice(front[0].length);
    for (const line of (front[1] ?? '').split('\n')) {
      const match = /^title:\s*(.+)$/.exec(line);
      if (match) title = (match[1] ?? '').trim().replace(/^["']|["']$/g, '');
    }
  }
  const lines = body.split('\n');
  const first = lines.findIndex((line) => line.trim().length > 0);
  const heading = first >= 0 ? /^#\s+(.+?)\s*#*\s*$/.exec(lines[first] ?? '') : null;
  if (heading) {
    title = title || (heading[1] ?? '').trim();
    lines.splice(first, 1);
  }
  const fallback = fileName
    .replace(/\.[^./\\]+$/, '')
    .replace(/[-_]+/g, ' ')
    .trim();
  return {
    title: (title || fallback || 'Untitled').slice(0, 300),
    content: lines.join('\n').trim(),
  };
}

/** How many [[links]] a text holds, which the author reviews after an import. */
export function countLinks(content: string): number {
  return (content.match(/\[\[[^\]\n]+\]\]/g) ?? []).length;
}
