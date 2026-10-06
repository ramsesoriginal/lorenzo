import { describe, expect, it } from 'vitest';
import type { PackItem } from './types';
import { looksLikeAPack, madeSummary, packNotRemoved, unpackQuestion } from './unpack';

const made = (title: string, quantity: number | null, ...children: PackItem[]): PackItem =>
  ({ item_instance: { title, quantity }, children }) as unknown as PackItem;

describe('looksLikeAPack', () => {
  it("recognises ADR 0145's contents list, nested or not", () => {
    expect(looksLikeAPack([{ content: 'This pack contains:\n\n- 1 x [Backpack](backpack)' }])).toBe(
      true,
    );
    expect(
      looksLikeAPack([{ content: '- 1 x [Backpack](backpack)\n  - 5 x [Rations](rations)' }]),
    ).toBe(true);
  });

  it('looks at every description, its own and the ones it inherits', () => {
    expect(
      looksLikeAPack([{ content: 'Canvas and leather.' }, { content: '- 2 x [Rope](rope)' }]),
    ).toBe(true);
  });

  it('is not fooled by prose, a plain list, or a link on its own', () => {
    expect(looksLikeAPack([])).toBe(false);
    expect(looksLikeAPack([{ content: 'Holds [[Rope]] and 2 x torches.' }])).toBe(false);
    expect(looksLikeAPack([{ content: '- a bulleted list\n- of things' }])).toBe(false);
    expect(looksLikeAPack([{ content: '- 2 x torches' }])).toBe(false);
  });
});

describe('what unpacking says', () => {
  const created = [
    made('Backpack', null, made('Rations', 5), made('Torch', 2)),
    made('Rope', null),
  ];

  it('lists what would be made, with counts and what is inside what', () => {
    expect(madeSummary(created)).toBe('Backpack (Rations ×5, Torch ×2), Rope');
  });

  it('asks with the list, and says the pack goes and it cannot be undone', () => {
    expect(unpackQuestion("Explorer's pack", created)).toBe(
      "Unpacking Explorer's pack makes Backpack (Rations ×5, Torch ×2), Rope, and the pack goes. This can't be undone.",
    );
  });

  it('says plainly when the contents are there but the pack is too', () => {
    expect(packNotRemoved('Not authorized.')).toBe(
      "The contents were added, but the pack itself couldn't be removed: Not authorized.",
    );
  });
});
