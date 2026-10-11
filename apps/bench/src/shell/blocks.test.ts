import { describe, expect, it } from 'vitest';
import {
  dropBlock,
  enterIn,
  joinBlocks,
  mergeUp,
  onFirstLine,
  onLastLine,
  splitBlock,
  splitBlocks,
} from './blocks';

describe('blocks', () => {
  it('splits a text at blank lines, and joins them with one', () => {
    expect(splitBlocks('One.\n\nTwo\nlines.\n\n\n\nThree.')).toEqual([
      'One.',
      'Two\nlines.',
      'Three.',
    ]);
    expect(joinBlocks(['One.', 'Two.'])).toBe('One.\n\nTwo.');
  });

  it('keeps a blank line inside a fenced block in that block', () => {
    expect(splitBlocks('```\na\n\nb\n```\n\nafter')).toEqual(['```\na\n\nb\n```', 'after']);
  });

  it('is one empty block for an empty text, so there is somewhere to type', () => {
    expect(splitBlocks('')).toEqual(['']);
    expect(splitBlocks('  \n\n ')).toEqual(['']);
  });

  it('reads windows line breaks', () => {
    expect(splitBlocks('a\r\n\r\nb')).toEqual(['a', 'b']);
  });

  it('knows whether the caret is on the first or the last line', () => {
    expect(onFirstLine('ab\ncd', 1)).toBe(true);
    expect(onFirstLine('ab\ncd', 4)).toBe(false);
    expect(onLastLine('ab\ncd', 4)).toBe(true);
    expect(onLastLine('ab\ncd', 1)).toBe(false);
  });
});

describe('Enter', () => {
  it('ends a paragraph, and what is after the caret starts the next', () => {
    expect(enterIn('Hello world', 5)).toEqual({ kind: 'split', before: 'Hello', after: ' world' });
    expect(enterIn('Hello', 5)).toEqual({ kind: 'split', before: 'Hello', after: '' });
  });

  it('goes on with a list, and numbers it', () => {
    expect(enterIn('- one', 5)).toEqual({ kind: 'newline', text: '- one\n- ', caret: 8 });
    expect(enterIn('1. one', 6)).toEqual({ kind: 'newline', text: '1. one\n2. ', caret: 10 });
  });

  it('ends a list on an empty item', () => {
    expect(enterIn('- one\n- ', 8)).toEqual({ kind: 'split', before: '- one', after: '' });
  });

  it('is a line break in a fenced block', () => {
    expect(enterIn('```\ncode', 8)).toEqual({ kind: 'newline', text: '```\ncode\n', caret: 9 });
  });
});

describe('editing the list of blocks', () => {
  it('splits a block in two', () => {
    expect(splitBlock(['a', 'b c', 'd'], 1, 'b', ' c')).toEqual(['a', 'b', ' c', 'd']);
  });

  it('joins a block onto the one before, with the caret where they meet', () => {
    expect(mergeUp(['ab', 'cd'], 1)).toEqual({ blocks: ['abcd'], active: 0, caret: 2 });
    expect(mergeUp(['ab'], 0)).toBeNull();
  });

  it('drops a block, and empties the only one', () => {
    expect(dropBlock(['a', 'b'], 0)).toEqual(['b']);
    expect(dropBlock(['a'], 0)).toEqual(['']);
  });
});
