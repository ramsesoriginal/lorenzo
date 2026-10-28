import { describe, expect, it } from 'vitest';
import { previewTarget } from './linkPreview';

describe('previewTarget', () => {
  it('reads the library and entity out of the links descriptions make', () => {
    expect(previewTarget('/item/?tenant=t1&id=e1')).toEqual({ tenant: 't1', id: 'e1' });
    expect(previewTarget('/board/?tenant=t1&character=c1')).toEqual({ tenant: 't1', id: 'c1' });
  });

  it('is null for anything else', () => {
    expect(previewTarget(null)).toBeNull();
    expect(previewTarget('/item/?tenant=t1&slug=sword')).toBeNull();
    expect(previewTarget('https://example.com/item/?tenant=t&id=e')).toBeNull();
    expect(previewTarget('#note')).toBeNull();
  });
});
