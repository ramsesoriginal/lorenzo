import { describe, expect, it } from 'vitest';
import { collectMoveTargets } from './moveTargets';
import type { EntitySummary, ItemInstance } from './types';

function makeItem(overrides: Partial<ItemInstance> = {}): ItemInstance {
  return {
    entity_id: 'item-1',
    title: 'Sword',
    quantity: 1,
    tags: [],
    weight: null,
    height: null,
    price: null,
    rarity: null,
    hp: null,
    armor: null,
    is_magical: null,
    is_cursed: null,
    is_container: null,
    descriptions: [],
    pictures: [],
    physical_stats: [],
    economic_stats: [],
    destroyable_stats: [],
    damaging_stats: [],
    created_by: null,
    updated_by: null,
    updated_at: '2026-01-01T00:00:00Z',
    prototype_ids: [],
    container_entity_id: null,
    owner_entity_id: null,
    slug: null,
    ...overrides,
  };
}

function makeContainer(overrides: Partial<EntitySummary> = {}): EntitySummary {
  return { id: 'container-1', name: 'Chest', quantity: null, ...overrides };
}

describe('collectMoveTargets', () => {
  it('includes an occupied container column', () => {
    const item = makeItem({ container_entity_id: null });
    const chest = makeContainer({ id: 'chest-1', name: 'Chest' });
    expect(collectMoveTargets(item, [chest], [])).toEqual([{ id: 'chest-1', name: 'Chest' }]);
  });

  it("excludes the item's own current container", () => {
    const item = makeItem({ container_entity_id: 'chest-1' });
    const chest = makeContainer({ id: 'chest-1', name: 'Chest' });
    expect(collectMoveTargets(item, [chest], [])).toEqual([]);
  });

  it('includes a currently-empty is_container card that has no column of its own', () => {
    const item = makeItem({ entity_id: 'item-1' });
    const backpack = makeItem({ entity_id: 'backpack-1', title: 'Backpack', is_container: true });
    expect(collectMoveTargets(item, [], [item, backpack])).toEqual([
      { id: 'backpack-1', name: 'Backpack' },
    ]);
  });

  it('excludes board cards that are not containers', () => {
    const item = makeItem({ entity_id: 'item-1' });
    const other = makeItem({ entity_id: 'other-1', title: 'Rock', is_container: false });
    expect(collectMoveTargets(item, [], [item, other])).toEqual([]);
  });

  it('excludes the item itself even if it is flagged as a container', () => {
    const item = makeItem({ entity_id: 'bag-1', title: 'Bag', is_container: true });
    expect(collectMoveTargets(item, [], [item])).toEqual([]);
  });

  it('de-duplicates a container that appears both as a column and as a flagged card', () => {
    const item = makeItem({ entity_id: 'item-1' });
    const chest = makeContainer({ id: 'chest-1', name: 'Chest' });
    const chestCard = makeItem({ entity_id: 'chest-1', title: 'Chest', is_container: true });
    expect(collectMoveTargets(item, [chest], [item, chestCard])).toEqual([
      { id: 'chest-1', name: 'Chest' },
    ]);
  });

  it('returns an empty list when nothing else on the board is a valid target', () => {
    const item = makeItem({ entity_id: 'item-1' });
    expect(collectMoveTargets(item, [], [item])).toEqual([]);
  });
});
