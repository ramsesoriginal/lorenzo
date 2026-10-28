import { describe, expect, it, vi } from 'vitest';

vi.mock('../src/lib/api', () => ({ client: {}, unwrap: vi.fn() }));

import { sourceOffset } from '../src/lib/manuscript-split';

describe('textarea caret to saved source offset', () => {
  it('counts astral characters as one source code point', () => {
    expect(sourceOffset('🐉.\n\nSecond', '🐉.\n\n'.length)).toBe(4);
  });
  it('retains CRLF characters absent from the textarea', () => {
    expect(sourceOffset('🐉.\r\n\r\nSecond', '🐉.\n\n'.length)).toBe(6);
  });
});
