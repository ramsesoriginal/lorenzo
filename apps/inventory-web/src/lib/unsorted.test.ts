import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  addUnsortedItem,
  detailsNote,
  findUnsortedItem,
  isUnsorted,
  readDraft,
  type UnsortedDraft,
} from './unsorted';

const calls = vi.hoisted(() => ({
  createItemInstance: vi.fn(),
  createInformation: vi.fn(),
  addKnower: vi.fn(),
  resolveSlugs: vi.fn(),
}));

vi.mock('./items', () => ({ createItemInstance: calls.createItemInstance }));
vi.mock('./information', () => ({
  createInformation: calls.createInformation,
  addKnower: calls.addKnower,
}));
vi.mock('./slugs', () => ({ resolveSlugs: calls.resolveSlugs }));

const draft = (overrides: Partial<UnsortedDraft> = {}): UnsortedDraft => ({
  name: 'Hydra Zahn',
  description: '',
  weight: '',
  value: '',
  ...overrides,
});

const read = (overrides: Partial<UnsortedDraft> = {}) => {
  const result = readDraft(draft(overrides));

  if (!result.ok) throw new Error(result.problem);

  return result.item;
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe('readDraft', () => {
  it('needs a name, trimmed', () => {
    expect(readDraft(draft({ name: '   ' }))).toEqual({ ok: false, problem: 'Give it a name.' });
    expect(read({ name: '  Hydra Zahn ' }).name).toBe('Hydra Zahn');
  });

  it('leaves out what is blank', () => {
    expect(read()).toEqual({ name: 'Hydra Zahn', description: null, weight: null, value: null });
  });

  it.each([
    ['0.5', 0.5],
    ['0,5', 0.5],
    ['2 lb', 2],
    ['2 LBS', 2],
    ['12 pounds', 12],
    ['  3 ', 3],
  ])('reads %s pounds as %s', (typed, pounds) => {
    expect(read({ weight: typed }).weight).toBe(pounds);
  });

  it.each(['heavy', '-1', '1 kg', '1.2.3', 'lb'])('does not read %s as pounds', (typed) => {
    const result = readDraft(draft({ weight: typed }));

    expect(result.ok).toBe(false);
  });
});

describe('detailsNote', () => {
  it('is a line for each, as the CLI writes it (ADR 0193)', () => {
    expect(detailsNote({ weight: 0.5, value: '2 gp' })).toBe('Weight: 0.5 lb\nValue: 2 gp');
    expect(detailsNote({ weight: 1, value: null })).toBe('Weight: 1 lb');
    expect(detailsNote({ weight: null, value: '?' })).toBe('Value: ?');
  });

  it('is nothing with neither', () => {
    expect(detailsNote({ weight: null, value: null })).toBeNull();
  });
});

describe('isUnsorted', () => {
  it('is whether the unsorted item is among the prototypes', () => {
    expect(isUnsorted({ prototype_ids: ['a', 'u'] }, 'u')).toBe(true);
    expect(isUnsorted({ prototype_ids: ['a'] }, 'u')).toBe(false);
  });

  it('is never, when the library has none', () => {
    expect(isUnsorted({ prototype_ids: ['a'] }, null)).toBe(false);
  });
});

describe('findUnsortedItem', () => {
  it('finds the item by its slug', async () => {
    calls.resolveSlugs.mockResolvedValue([{ slug: 'unsorted', entity_id: 'u', kinds: ['item'] }]);

    expect(await findUnsortedItem('t')).toBe('u');
    expect(calls.resolveSlugs).toHaveBeenCalledWith('t', ['unsorted']);
  });

  it('finds none when there is no such slug, or it names something that is not an item', async () => {
    calls.resolveSlugs.mockResolvedValue([]);
    expect(await findUnsortedItem('t')).toBeNull();

    calls.resolveSlugs.mockResolvedValue([{ slug: 'unsorted', entity_id: 'x', kinds: ['being'] }]);
    expect(await findUnsortedItem('t')).toBeNull();
  });
});

describe('addUnsortedItem', () => {
  beforeEach(() => {
    calls.createItemInstance.mockResolvedValue({ entity_id: 'i', title: 'Hydra Zahn' });
    calls.createInformation.mockImplementation(async (_t, _e, note) => ({ id: `n-${note.title}` }));
  });

  it("makes it in the player's name, owned, then writes and tells each note to the character", async () => {
    const added = await addUnsortedItem(
      't',
      'u',
      'owner',
      read({ description: 'from the cave', weight: '1', value: '?' }),
    );

    expect(calls.createItemInstance).toHaveBeenCalledWith(
      't',
      'u',
      'owner',
      undefined,
      'Hydra Zahn',
    );
    expect(calls.createInformation.mock.calls.map(([, entity, note]) => [entity, note])).toEqual([
      ['i', { title: 'Note', type: 'note', isPublic: false, content: 'from the cave' }],
      ['i', { title: 'Details', type: 'note', isPublic: false, content: 'Weight: 1 lb\nValue: ?' }],
    ]);
    expect(calls.addKnower.mock.calls).toEqual([
      ['t', 'n-Note', 'owner'],
      ['t', 'n-Details', 'owner'],
    ]);
    expect(added).toEqual({ instance: { entity_id: 'i', title: 'Hydra Zahn' }, notesNotSaved: [] });
  });

  it('writes no note it has nothing for', async () => {
    await addUnsortedItem('t', 'u', 'owner', read());

    expect(calls.createInformation).not.toHaveBeenCalled();
  });

  it('keeps the item and says which note was not saved', async () => {
    calls.createInformation.mockImplementation(async (_t, _e, note) => {
      if (note.title === 'Note') throw new Error('refused');

      return { id: 'n-Details' };
    });

    const added = await addUnsortedItem('t', 'u', 'owner', read({ description: 'x', weight: '1' }));

    expect(added.notesNotSaved).toEqual(['Note']);
    expect(added.instance.entity_id).toBe('i');
    expect(calls.addKnower).toHaveBeenCalledTimes(1); // the one that was saved is still told
  });

  it('does not write notes for an item that could not be made', async () => {
    calls.createItemInstance.mockRejectedValue(new Error('switched off'));

    await expect(addUnsortedItem('t', 'u', 'owner', read({ description: 'x' }))).rejects.toThrow(
      'switched off',
    );
    expect(calls.createInformation).not.toHaveBeenCalled();
  });
});
