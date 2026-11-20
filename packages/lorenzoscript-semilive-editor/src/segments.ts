// The text as blocks (ADR 0509): where each top-level block starts and ends, in characters.
import { blockRanges } from '@lorenzo/lorenzoscript';

export type Segment = {
  /** The first character of the block. */
  from: number;
  /** One past its last character; the blank lines after it are not part of it. */
  to: number;
  /** The block's type, or `definition` for a footnote or abbreviation definition. */
  type: string;
};

/** The blocks of a source, with their character spans. */
export function segmentsOf(source: string): Segment[] {
  const starts: number[] = [];
  const lines = source.split('\n');
  let at = 0;
  for (const line of lines) {
    starts.push(at);
    at += line.length + 1;
  }
  return blockRanges(source).map((range) => {
    const last = lines[range.end - 1] ?? '';
    return {
      from: starts[range.start] ?? 0,
      to: (starts[range.end - 1] ?? 0) + last.length,
      type: range.type,
    };
  });
}

/** The definitions to render with a block that refers to a footnote. */
export function definitionsFor(source: string, segments: readonly Segment[], own: Segment) {
  if (!source.slice(own.from, own.to).includes('[^')) return '';
  return segments
    .filter((s) => s.type === 'definition' && s !== own)
    .map((s) => source.slice(s.from, s.to))
    .join('\n');
}

/**
 * Where in a block's source a click on its rendered text falls. The text node that was clicked
 * is found in the source by its opening words; with no match, the click's share of the text
 * stands in for it. A caret in the right paragraph, close to the right word, is the aim.
 */
export function caretInSource(source: string, nodeText: string, offset: number, share = 1): number {
  const words = nodeText.trimStart();
  const lead = nodeText.length - words.length;
  const needle = words.slice(0, 24);
  if (needle) {
    const found = source.indexOf(needle);
    if (found >= 0) return Math.min(source.length, Math.max(0, found + offset - lead));
  }
  return Math.round(Math.min(1, Math.max(0, share)) * source.length);
}
