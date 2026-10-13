import { LorenzoApiError } from '@lorenzo/api-client';
import { describe, expect, it, vi } from 'vitest';
import { type Card, createCardCache, kindLabel, previewTarget, statText } from './linkPreview';

const card = (name: string) => ({ name }) as Card;

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

describe('kindLabel and statText', () => {
  it('names the most specific kind in the words of the product', () => {
    expect(kindLabel(['being', 'character'])).toBe('Character');
    expect(kindLabel(['item_instance'])).toBe('Inventory item');
    expect(kindLabel(['item'])).toBe('Item');
    expect(kindLabel([])).toBe('Entry');
  });

  it('writes a stat as a name and a value', () => {
    expect(statText({ name: 'hit_points', value: 9 })).toBe('hit points 9');
  });
});

describe('createCardCache', () => {
  it('asks once per entity for the page', async () => {
    const fetchCard = vi.fn(async (_t: string, id: string) => card(id));
    const load = createCardCache(fetchCard);

    expect(await load('t', 'a')).toEqual(card('a'));
    await load('t', 'a');
    await load('t', 'b');

    expect(fetchCard).toHaveBeenCalledTimes(2);
  });

  it('remembers a missing entry but asks again after any other failure', async () => {
    const fetchCard = vi
      .fn<(t: string, id: string) => Promise<Card>>()
      .mockRejectedValueOnce(new LorenzoApiError('gone', 404))
      .mockRejectedValueOnce(new LorenzoApiError('down', 503))
      .mockResolvedValue(card('x'));
    const load = createCardCache(fetchCard);

    expect(await load('t', 'missing')).toBeNull();
    expect(await load('t', 'missing')).toBeNull();
    expect(fetchCard).toHaveBeenCalledTimes(1);

    expect(await load('t', 'flaky')).toBeNull();
    expect(await load('t', 'flaky')).toEqual(card('x'));
    expect(fetchCard).toHaveBeenCalledTimes(3);
  });
});
