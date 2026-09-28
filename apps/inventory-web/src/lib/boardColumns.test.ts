import { describe, expect, it } from 'vitest';
import { controlledBoard, ownerMark, unownedBoard } from './boardColumns';
import type { ControlledColumn, EntitySummary, ItemInstance } from './types';

const entity = (id: string, name: string): EntitySummary => ({ id, name, quantity: null });

function item(id: string, owner: string | null): ItemInstance {
  return { entity_id: id, owner_entity_id: owner } as ItemInstance;
}

type ControlledItem = ControlledColumn['item_instances'][number];

function controlledItem(id: string, owner: string | null): ControlledItem {
  return { ...item(id, owner), visible_to_characters: true } as ControlledItem;
}

function column(
  kind: ControlledColumn['kind'],
  container: EntitySummary | null,
  overrides: Partial<Omit<ControlledColumn, 'kind' | 'container'>> = {},
): ControlledColumn {
  return {
    kind,
    container,
    container_kind: container ? 'item_instance' : null,
    path: [],
    carried: false,
    contents_hidden: false,
    item_instances: [],
    ...overrides,
  };
}

const alice = entity('alice', 'Alice');
const brisk = entity('brisk', 'Brisk');
const backpack = entity('backpack', 'Backpack');
const pouch = entity('pouch', 'Belt pouch');
const bag = entity('bag', 'Bag');
const chest = entity('chest', 'Chest');
const carriage = entity('carriage', 'Carriage');
const stable = entity('stable', 'Stable');
const kase = entity('case', 'Case');

describe('controlledBoard', () => {
  const board = controlledBoard(
    {
      columns: [
        column('equipped', alice, {
          container_kind: 'being',
          carried: true,
          item_instances: [controlledItem('sword', 'alice')],
        }),
        column('not_carried', null),
        column('container', backpack, { carried: true }),
        column('container', pouch, { carried: true, path: [backpack] }),
        column('container', bag, { carried: true, contents_hidden: true }),
        column('container', chest),
        column('container', carriage, { path: [stable] }),
        column('read_only', brisk, { container_kind: 'being' }),
        column('read_only', kase, { path: [brisk] }),
        column('read_only', stable, { container_kind: 'other' }),
      ],
      owners: [alice, brisk],
    },
    'alice',
  );

  it('keeps the order controlled-by gives, Equipped and Not carried first', () => {
    expect(board.columns.map((c) => c.title)).toEqual([
      'Equipped',
      'Not carried',
      'Backpack',
      'Belt pouch',
      'Bag',
      'Chest',
      'Carriage',
      'Brisk',
      'Case',
      'Stable',
    ]);
    expect(board.columns.filter((c) => c.fixed).map((c) => c.title)).toEqual([
      'Equipped',
      'Not carried',
    ]);
  });

  it('drops into the being on Equipped, out of every container on Not carried', () => {
    const [equipped, notCarried] = board.columns;
    expect(equipped).toMatchObject({
      key: 'alice',
      droppable: true,
      dropTarget: 'alice',
      empty: 'Nothing equipped.',
    });
    expect(equipped?.items.map((i) => i.entity_id)).toEqual(['sword']);
    expect(notCarried).toMatchObject({ key: 'loose', droppable: true, dropTarget: null });
  });

  it('drops into a container, and not into a read-only column', () => {
    const byTitle = new Map(board.columns.map((c) => [c.title, c]));
    expect(byTitle.get('Backpack')).toMatchObject({ droppable: true, dropTarget: 'backpack' });
    expect(byTitle.get('Case')).toMatchObject({ droppable: false, dropTarget: null });
  });

  it('says where each container is', () => {
    expect(board.columns.map((c) => [c.title, c.note])).toEqual([
      ['Equipped', null],
      ['Not carried', null],
      ['Backpack', null],
      ['Belt pouch', 'In Backpack'],
      ['Bag', null],
      ['Chest', 'Not carried'],
      ['Carriage', 'In Stable'],
      ['Brisk', 'Brisk has these'],
      ['Case', 'In Brisk'],
      // A place isn't carried or not; it just is.
      ['Stable', null],
    ]);
  });

  it('passes on when a column holds more than it lists', () => {
    const hidden = board.columns.filter((c) => c.contentsHidden).map((c) => c.title);
    expect(hidden).toEqual(['Bag']);
  });

  it("has no Equipped on a group's board, and knows whose board it is", () => {
    const groupBoard = controlledBoard(
      { columns: [column('not_carried', null)], owners: [] },
      'company',
    );
    expect(groupBoard.columns.map((c) => c.title)).toEqual(['Not carried']);
    expect(groupBoard.holderId).toBe('company');
    expect(groupBoard.holderIsBeing).toBe(false);
    expect(board.holderIsBeing).toBe(true);
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
    expect(board.columns.map((c) => [c.key, c.dropTarget, c.title])).toEqual([
      ['loose', null, 'Unowned'],
      ['chest', 'chest', 'Chest'],
    ]);
    expect(board.columns.some((c) => c.fixed)).toBe(false);
    expect(board.holderId).toBeNull();
  });
});

describe('ownerMark', () => {
  const board = controlledBoard(
    { columns: [column('equipped', alice, { container_kind: 'being' })], owners: [alice, brisk] },
    'alice',
  );

  it("marks a group's things with the group's name", () => {
    const company = entity('company', 'The Company');
    const withCompany = controlledBoard(
      { columns: [column('equipped', alice)], owners: [alice, company] },
      'alice',
    );
    expect(ownerMark(item('rope', 'company'), withCompany)).toBe("The Company's");
  });

  it("marks someone else's things, and unowned ones", () => {
    expect(ownerMark(item('potion', 'brisk'), board)).toBe("Brisk's");
    expect(ownerMark(item('map', null), board)).toBe("No one's");
    expect(ownerMark(item('coin', 'stranger'), board)).toBe("Someone else's");
  });

  it("doesn't mark the being's own things, or anything on the unowned board", () => {
    expect(ownerMark(item('sword', 'alice'), board)).toBeNull();
    const unowned = unownedBoard({ groups: [] });
    expect(ownerMark(item('map', null), unowned)).toBeNull();
  });
});
