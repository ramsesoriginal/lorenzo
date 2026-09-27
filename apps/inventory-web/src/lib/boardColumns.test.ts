import { describe, expect, it } from 'vitest';
import { heldBoard, ownerMark, unownedBoard } from './boardColumns';
import type { EntitySummary, HeldGroup, ItemInstance } from './types';

const entity = (id: string, name: string): EntitySummary => ({ id, name, quantity: null });

function item(id: string, owner: string | null): ItemInstance {
  return { entity_id: id, owner_entity_id: owner } as ItemInstance;
}

function group(
  container: EntitySummary,
  overrides: Partial<Omit<HeldGroup, 'container'>> = {},
): HeldGroup {
  return {
    container,
    container_kind: 'item_instance',
    path: [],
    carried: true,
    item_instances: [],
    ...overrides,
  };
}

const alice = entity('alice', 'Alice');
const pia = entity('pia', 'Pia');
const backpack = entity('backpack', 'Backpack');
const pouch = entity('pouch', 'Belt pouch');
const carriage = entity('carriage', 'Carriage');
const chest = entity('chest', 'Chest');
const stable = entity('stable', 'Stable');
const tavern = entity('tavern', 'Tavern');

describe('heldBoard', () => {
  const board = heldBoard({
    groups: [
      group(alice, { container_kind: 'being', item_instances: [item('sword', 'alice')] }),
      group(backpack),
      group(pouch, { path: [backpack] }),
      group(pia, { container_kind: 'being', carried: false, path: [tavern] }),
      group(chest, { carried: false, path: [carriage, stable] }),
    ],
    owners: [alice, pia],
  });

  it('puts Equipped first, as somewhere to drop into the being', () => {
    const [equipped] = board.carried;
    expect(equipped).toMatchObject({
      key: 'alice',
      dropTarget: 'alice',
      title: 'Equipped',
      note: null,
      empty: 'Nothing equipped.',
    });
    expect(equipped?.items.map((i) => i.entity_id)).toEqual(['sword']);
  });

  it('says where a nested carried container is', () => {
    expect(board.carried.map((c) => [c.title, c.note])).toEqual([
      ['Equipped', null],
      ['Backpack', null],
      ['Belt pouch', 'In Backpack'],
    ]);
  });

  it('keeps what is held elsewhere apart, saying where it is or who has it', () => {
    expect(board.elsewhere.map((c) => [c.title, c.note])).toEqual([
      ['Pia', 'Pia has these, in Tavern'],
      ['Chest', 'In Carriage, in Stable'],
    ]);
  });

  it("names a holder that isn't a being by its own name", () => {
    const company = entity('company', 'The Company');
    const groupBoard = heldBoard({
      groups: [group(company, { container_kind: 'other' })],
      owners: [],
    });
    expect(groupBoard.carried[0]?.title).toBe('The Company');
    // Nothing goes *into* a group: dropping on its column takes a card out of every container.
    expect(groupBoard.carried[0]?.dropTarget).toBeNull();
    expect(groupBoard.holderIsBeing).toBe(false);
  });
});

describe('unownedBoard', () => {
  it('reads what is in no container first, and dropping there takes it out of every one', () => {
    const board = unownedBoard({
      groups: [
        { container: chest, item_instances: [] },
        { container: null, item_instances: [] },
      ],
    });
    expect(board.carried.map((c) => [c.key, c.dropTarget, c.title])).toEqual([
      ['loose', null, 'Unowned'],
      ['chest', 'chest', 'Chest'],
    ]);
    expect(board.holderId).toBeNull();
  });
});

describe('ownerMark', () => {
  const board = heldBoard({
    groups: [group(alice, { container_kind: 'being' })],
    owners: [alice, pia],
  });

  it("marks a group's things with the group's name", () => {
    const company = entity('company', 'The Company');
    const withCompany = heldBoard({
      groups: [group(alice, { container_kind: 'being' })],
      owners: [alice, company],
    });
    expect(ownerMark(item('rope', 'company'), withCompany)).toBe("The Company's");
  });

  it("marks someone else's things, and unowned ones", () => {
    expect(ownerMark(item('potion', 'pia'), board)).toBe("Pia's");
    expect(ownerMark(item('map', null), board)).toBe("No one's");
    expect(ownerMark(item('coin', 'stranger'), board)).toBe("Someone else's");
  });

  it("doesn't mark the being's own things, or anything on the unowned board", () => {
    expect(ownerMark(item('sword', 'alice'), board)).toBeNull();
    const unowned = unownedBoard({ groups: [] });
    expect(ownerMark(item('map', null), unowned)).toBeNull();
  });
});
