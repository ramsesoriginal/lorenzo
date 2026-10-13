// The blocks of a text and what the keys do to them, as plain data: the live editor shows the
// block with the caret as source and the rest drawn, so a text is a list of blocks. No DOM, so it
// is tested alone.

const FENCE = /^\s*(```|~~~)/;

/**
 * A text as its blocks: runs of lines between blank lines. A blank line inside a fenced code block
 * does not end it. An empty text is one empty block, so there is always somewhere to type.
 */
export function splitBlocks(text: string): string[] {
  const blocks: string[] = [];
  let current: string[] = [];
  let fenced = false;
  for (const line of text.replace(/\r\n?/g, '\n').split('\n')) {
    if (FENCE.test(line)) fenced = !fenced;
    if (line.trim() === '' && !fenced) {
      if (current.length) blocks.push(current.join('\n'));
      current = [];
    } else current.push(line);
  }
  if (current.length) blocks.push(current.join('\n'));
  return blocks.length ? blocks : [''];
}

/** The blocks as a text: one blank line between them. */
export const joinBlocks = (blocks: readonly string[]): string => blocks.join('\n\n');

/** Whether the caret is on the first line of the block (nothing before it is a line break). */
export const onFirstLine = (text: string, caret: number): boolean =>
  !text.slice(0, caret).includes('\n');

/** Whether the caret is on the last line of the block. */
export const onLastLine = (text: string, caret: number): boolean =>
  !text.slice(caret).includes('\n');

/** Inside a fenced code block at the caret: an odd number of fence lines before it. */
function inFence(text: string, caret: number): boolean {
  return (
    text
      .slice(0, caret)
      .split('\n')
      .filter((l) => FENCE.test(l)).length %
      2 ===
    1
  );
}

const LIST = /^(\s*)([-*+]|\d+[.)])\s+/;

export type Enter =
  /** Put a line break in the block, and the caret after `text`'s `caret`. */
  | { kind: 'newline'; text: string; caret: number }
  /** End the block here: `before` stays, `after` starts the next. */
  | { kind: 'split'; before: string; after: string };

/**
 * What Enter does in a block. In a list it goes on with the list (the next number, the same
 * marker), and Enter on an empty item ends the list. In a fenced block it is a line break. Anywhere
 * else it ends the block, and what is after the caret starts a new one.
 */
export function enterIn(text: string, caret: number): Enter {
  if (inFence(text, caret))
    return {
      kind: 'newline',
      text: `${text.slice(0, caret)}\n${text.slice(caret)}`,
      caret: caret + 1,
    };
  const lineStart = text.lastIndexOf('\n', caret - 1) + 1;
  const line = text.slice(lineStart, caret);
  const marker = LIST.exec(text.slice(lineStart).split('\n')[0] ?? '');
  if (marker) {
    const rest = line.slice(marker[0].length);
    if (rest.trim() === '' && caret === text.length) {
      // An empty item ends the list: the item goes and a new block starts.
      return { kind: 'split', before: text.slice(0, lineStart).replace(/\n$/, ''), after: '' };
    }
    const bullet = /^\d/.test(marker[2] ?? '')
      ? `${Number.parseInt(marker[2] ?? '0', 10) + 1}${(marker[2] ?? '').slice(-1)}`
      : (marker[2] ?? '-');
    const next = `\n${marker[1] ?? ''}${bullet} `;
    return {
      kind: 'newline',
      text: `${text.slice(0, caret)}${next}${text.slice(caret)}`,
      caret: caret + next.length,
    };
  }
  return { kind: 'split', before: text.slice(0, caret), after: text.slice(caret) };
}

/** Puts `after` as a new block after block `i`, with `before` as block `i`. */
export function splitBlock(
  blocks: readonly string[],
  i: number,
  before: string,
  after: string,
): string[] {
  return [...blocks.slice(0, i), before, after, ...blocks.slice(i + 1)];
}

/** Joins block `i` onto the one before it, with the caret where they meet; null for the first. */
export function mergeUp(
  blocks: readonly string[],
  i: number,
): { blocks: string[]; active: number; caret: number } | null {
  if (i <= 0) return null;
  const prev = blocks[i - 1] ?? '';
  return {
    blocks: [...blocks.slice(0, i - 1), prev + (blocks[i] ?? ''), ...blocks.slice(i + 1)],
    active: i - 1,
    caret: prev.length,
  };
}

/** Takes block `i` away, unless it is the only one (then it is emptied). */
export function dropBlock(blocks: readonly string[], i: number): string[] {
  if (blocks.length <= 1) return [''];
  return [...blocks.slice(0, i), ...blocks.slice(i + 1)];
}
