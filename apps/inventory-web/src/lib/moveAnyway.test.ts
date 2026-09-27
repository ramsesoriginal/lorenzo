import { describe, expect, it, vi } from 'vitest';
import { LorenzoApiError } from './api';
import { bulkMoveAnywayQuestion, isOverCapacity, moveOrAsk, overCapacityIds } from './moveAnyway';
import type { BulkResultItem } from './types';

vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

const full = new LorenzoApiError(
  'Backpack can carry 20, and this would make it 26.',
  409,
  'capacity-exceeded',
);

describe('moveOrAsk', () => {
  it('moves once when the move fits', async () => {
    const move = vi.fn(async () => undefined);
    const ask = vi.fn(() => true);

    await moveOrAsk(move, { canOverride: true, ask });

    expect(move.mock.calls).toEqual([[false]]);
    expect(ask).not.toHaveBeenCalled();
  });

  it('asks a GM, and moves anyway on a yes', async () => {
    const move = vi.fn(async (override: boolean) => {
      if (!override) throw full;
    });
    const ask = vi.fn(() => true);

    await moveOrAsk(move, { canOverride: true, ask });

    expect(ask).toHaveBeenCalledWith(
      'Backpack can carry 20, and this would make it 26. Move anyway?',
    );
    expect(move.mock.calls).toEqual([[false], [true]]);
  });

  it('keeps the refusal on a no', async () => {
    const move = vi.fn(async () => {
      throw full;
    });

    await expect(moveOrAsk(move, { canOverride: true, ask: () => false })).rejects.toBe(full);
    expect(move).toHaveBeenCalledTimes(1);
  });

  it("doesn't ask someone who can't override", async () => {
    const ask = vi.fn(() => true);
    const move = vi.fn(async () => {
      throw full;
    });

    await expect(moveOrAsk(move, { canOverride: false, ask })).rejects.toBe(full);
    expect(ask).not.toHaveBeenCalled();
  });

  it("doesn't ask about any other refusal", async () => {
    const other = new LorenzoApiError('Not yours.', 403, 'item-not-yours-to-give');
    const ask = vi.fn(() => true);

    await expect(
      moveOrAsk(
        async () => {
          throw other;
        },
        { canOverride: true, ask },
      ),
    ).rejects.toBe(other);
    expect(ask).not.toHaveBeenCalled();
    expect(isOverCapacity(other)).toBe(false);
  });
});

describe('bulk moves', () => {
  function result(id: string, problem?: { type: string; detail: string }): BulkResultItem {
    return problem
      ? { entity_id: id, status: 'error', problem: { ...problem, title: 'No', status: 409 } }
      : { entity_id: id, status: 'ok' };
  }
  const refused = (id: string, detail: string) => result(id, { type: 'capacity-exceeded', detail });

  it('finds the entries refused for capacity, and only those', () => {
    const results = [
      result('rope'),
      refused('anvil', 'Backpack can carry 20, and this would make it 60.'),
      result('ring', { type: 'item-not-yours-to-give', detail: 'Not yours.' }),
    ];
    expect(overCapacityIds(results)).toEqual(['anvil']);
    expect(bulkMoveAnywayQuestion(results)).toBe(
      'Backpack can carry 20, and this would make it 60. Move anyway?',
    );
  });

  it('asks once for several', () => {
    const results = [
      refused('anvil', 'Backpack can carry 20, and this would make it 60.'),
      refused('boulder', 'Backpack can carry 20, and this would make it 45.'),
    ];
    expect(bulkMoveAnywayQuestion(results)).toBe(
      "2 of them don't fit. Backpack can carry 20, and this would make it 60. Move them anyway?",
    );
  });

  it('asks nothing when nothing was refused for capacity', () => {
    expect(bulkMoveAnywayQuestion([result('rope')])).toBeNull();
  });
});
