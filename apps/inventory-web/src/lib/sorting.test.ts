import { beforeEach, describe, expect, it, vi } from 'vitest';
import { assignAll, descriptionFrom, groupUnsorted } from './sorting';
import type { ItemInstance } from './types';

const calls = vi.hoisted(() => ({ setInstancePrototype: vi.fn() }));

vi.mock('./items', () => ({
  setInstancePrototype: calls.setInstancePrototype,
  createCatalogItem: vi.fn(),
  getEntityDetail: vi.fn(),
}));
vi.mock('./information', () => ({
  descriptionDraft: vi.fn(),
  listInformation: vi.fn(),
  saveDescription: vi.fn(),
  textOf: vi.fn(),
}));
vi.mock('./api', () => ({
  client: {},
  fetchAllPages: vi.fn(),
  MAX_PAGE_SIZE: 100,
  unwrap: vi.fn(),
}));

const instance = (id: string, title: string) => ({ entity_id: id, title }) as ItemInstance;

beforeEach(() => calls.setInstancePrototype.mockReset());

describe('groupUnsorted', () => {
  it('puts names that differ only in case, accents or punctuation together', () => {
    const groups = groupUnsorted([
      instance('1', 'Torch'),
      instance('2', 'torch.'),
      instance('3', 'Torch'),
      instance('4', 'Rope'),
    ]);

    expect(groups.map((g) => [g.name, g.instances.length])).toEqual([
      ['Torch', 3],
      ['Rope', 1],
    ]);
  });

  it('names a group by the spelling most used, and orders ties by name', () => {
    const groups = groupUnsorted([
      instance('1', 'torch'),
      instance('2', 'Torch'),
      instance('3', 'Torch'),
      instance('4', 'Anvil'),
      instance('5', 'Zither'),
    ]);

    expect(groups.map((g) => g.name)).toEqual(['Torch', 'Anvil', 'Zither']);
  });

  it('names a tie the same way whatever the order', () => {
    const names = (order: string[]) =>
      groupUnsorted(order.map((title, at) => instance(String(at), title)))[0]?.name;

    expect(names(['torch.', 'Torch'])).toBe('Torch');
    expect(names(['Torch', 'torch.'])).toBe('Torch');
  });

  it('gives a name of only punctuation a group of its own', () => {
    expect(groupUnsorted([instance('1', '???'), instance('2', '!!')])).toHaveLength(2);
  });
});

describe('assignAll', () => {
  it('sorts each in turn and reports progress', async () => {
    calls.setInstancePrototype.mockResolvedValue({});
    const seen: string[] = [];

    const sorted = await assignAll('t', [instance('1', 'A'), instance('2', 'B')], 'torch', (d, n) =>
      seen.push(`${d}/${n}`),
    );

    expect(sorted.done).toHaveLength(2);
    expect(seen).toEqual(['1/2', '2/2']);
    expect(calls.setInstancePrototype).toHaveBeenNthCalledWith(1, 't', '1', 'torch');
  });

  it('carries on past a failure and says which one failed', async () => {
    calls.setInstancePrototype
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error('No.'))
      .mockResolvedValueOnce({});

    const sorted = await assignAll(
      't',
      [instance('1', 'A'), instance('2', 'B'), instance('3', 'C')],
      'torch',
    );

    expect(sorted.done.map((d) => d.entity_id)).toEqual(['1', '3']);
    expect(sorted.failed.map((f) => f.instance.entity_id)).toEqual(['2']);
    expect(sorted.failed[0]?.problem).toContain('No.');
  });
});

describe('descriptionFrom', () => {
  it('is the first note called Note, and nothing without one', () => {
    expect(
      descriptionFrom([
        { title: 'Details', text: 'Weight: 1 lb' },
        { title: 'Note', text: 'burns' },
      ]),
    ).toBe('burns');
    expect(descriptionFrom([{ title: 'Details', text: 'x' }])).toBeNull();
  });
});
