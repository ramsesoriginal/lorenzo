import { describe, expect, it, vi } from 'vitest';

// The sign-in library needs a browser; nothing here signs in.
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

import { descriptionOf, pictureOf, summariseInventory } from './being';

const item = (title: string, quantity: number | null) => ({ title, quantity }) as never;

describe('summariseInventory', () => {
  it('counts entries and pieces across containers, and names the first few', () => {
    const summary = summariseInventory(
      {
        groups: [
          { container: null, item_instances: [item('Rope', 2), item('Axe', null)] },
          { container: { id: 'c', name: 'Sack' }, item_instances: [item('Coin', 30)] },
        ],
      },
      2,
    );

    expect(summary).toEqual({
      entries: 3,
      pieces: 33,
      top: [
        { name: 'Axe', quantity: 1 },
        { name: 'Coin', quantity: 30 },
      ],
      more: 1,
    });
  });

  it('is empty for a being that carries nothing', () => {
    expect(summariseInventory({ groups: [] })).toMatchObject({ entries: 0, pieces: 0, more: 0 });
  });
});

describe('descriptionOf and pictureOf', () => {
  const entity = {
    information: [
      { type: 'note', payloads: [{ kind: 'description', content: 'a note' }] },
      { type: 'description', payloads: [{ kind: 'description', content: 'Tall.' }] },
      { type: 'main_picture', payloads: [{ kind: 'picture', id: 'p1' }] },
    ],
  } as never;

  it('takes the description information, not a note', () => {
    expect(descriptionOf(entity)).toBe('Tall.');
    expect(descriptionOf({ information: [] })).toBe('');
  });

  it('takes the main picture payload', () => {
    expect(pictureOf(entity)).toMatchObject({ id: 'p1' });
    expect(pictureOf({ information: [] })).toBeUndefined();
  });
});
