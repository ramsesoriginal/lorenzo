import { beforeEach, describe, expect, it, vi } from 'vitest';
import { type AddItemViewer, addItemStanding, type Seat } from './addItem';

const found = vi.hoisted(() => ({ findCatalogItems: vi.fn() }));
vi.mock('./items', () => found);

const alice = 'char-alice';
const seat = (self_service_effective: boolean, ...characters: string[]): Seat => ({
  characters: characters.map((entity_id) => ({ entity_id })),
  self_service_effective,
});
const viewer = (overrides: Partial<AddItemViewer> = {}): AddItemViewer => ({
  viewerIsGm: false,
  holderId: alice,
  seats: [seat(true, alice)],
  ...overrides,
});

describe('addItemStanding', () => {
  it("offers a player adding to their own character when it's on", () => {
    expect(addItemStanding(viewer())).toBe('allowed');
  });

  it('says it is off when every seat that plays the character is off', () => {
    expect(addItemStanding(viewer({ seats: [seat(false, alice), seat(false, alice)] }))).toBe(
      'off',
    );
  });

  it('is on when any one seat that plays the character is on, as the API reads it (ADR 0186)', () => {
    expect(addItemStanding(viewer({ seats: [seat(false, alice), seat(true, alice)] }))).toBe(
      'allowed',
    );
  });

  it("doesn't count a seat that plays someone else", () => {
    expect(addItemStanding(viewer({ seats: [seat(true, 'char-bob'), seat(false, alice)] }))).toBe(
      'off',
    );
  });

  it("shows nothing on a player's own board of somebody else's character", () => {
    expect(addItemStanding(viewer({ holderId: 'char-bob' }))).toBe('hidden');
    expect(addItemStanding(viewer({ seats: [] }))).toBe('hidden');
  });

  it("shows nothing on a group's or the unowned board, whoever looks", () => {
    expect(addItemStanding(viewer({ holderId: null }))).toBe('hidden');
    expect(addItemStanding(viewer({ holderId: null, viewerIsGm: true }))).toBe('hidden');
  });

  it("offers a GM any being's board, whatever the switch says: a manager is the API's to judge", () => {
    expect(addItemStanding(viewer({ viewerIsGm: true, holderId: 'char-bob', seats: [] }))).toBe(
      'allowed',
    );
    expect(addItemStanding(viewer({ viewerIsGm: true, seats: [seat(false, alice)] }))).toBe(
      'allowed',
    );
  });
});

describe('searchAddableItems', () => {
  beforeEach(() => found.findCatalogItems.mockReset());

  it('offers the first few items, labelled by title', async () => {
    const { searchAddableItems } = await import('./addItem');
    const sword = { entity_id: 'sword', title: "Aldric's blade", name: 'Sword' };
    found.findCatalogItems.mockResolvedValue([sword]);

    await expect(searchAddableItems('tenant-1', '')).resolves.toEqual([
      { label: "Aldric's blade", value: sword },
    ]);
    expect(found.findCatalogItems).toHaveBeenCalledWith('tenant-1', '', 8);
  });

  it('passes what was typed on', async () => {
    const { searchAddableItems } = await import('./addItem');
    found.findCatalogItems.mockResolvedValue([]);

    await expect(searchAddableItems('tenant-1', 'rope')).resolves.toEqual([]);
    expect(found.findCatalogItems).toHaveBeenCalledWith('tenant-1', 'rope', 8);
  });
});
