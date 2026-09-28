import { describe, expect, it, vi } from 'vitest';
import { LorenzoApiError } from './api';
import type { AnywayFlags } from './items';
import {
  bulkMoveAnywayQuestion,
  giveOrAsk,
  isOverridable,
  LIFT_QUESTION,
  moveOrAsk,
  overridableIds,
} from './moveAnyway';
import type { BulkResultItem } from './types';

vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

const full = new LorenzoApiError(
  'Backpack can carry 20, and this would make it 26.',
  409,
  'capacity-exceeded',
);
const bound = new LorenzoApiError(
  "Ring is bound to Ashfang (binds on equip), so it can't be taken off Ashfang.",
  409,
  'item-bound',
);

/** A write refused with `refusal` until it's overridden. */
function refusedUnlessOverridden(refusal: LorenzoApiError) {
  return vi.fn(async (flags: AnywayFlags) => {
    if (!flags.override) throw refusal;
  });
}

describe('moveOrAsk', () => {
  it('moves once when the move fits', async () => {
    const move = vi.fn(async () => undefined);
    const ask = vi.fn(() => true);

    await moveOrAsk(move, { canOverride: true, ask });

    expect(move.mock.calls).toEqual([[{}]]);
    expect(ask).not.toHaveBeenCalled();
  });

  it('asks a GM, and moves anyway on a yes', async () => {
    const move = refusedUnlessOverridden(full);
    const ask = vi.fn(() => true);

    await moveOrAsk(move, { canOverride: true, ask });

    expect(ask.mock.calls).toEqual([
      ['Backpack can carry 20, and this would make it 26. Move anyway?'],
    ]);
    expect(move.mock.calls).toEqual([[{}], [{ override: true, liftBinding: false }]]);
  });

  it('asks a GM about lifting a binding too', async () => {
    const move = refusedUnlessOverridden(bound);
    const ask = vi.fn(() => true);

    await moveOrAsk(move, { canOverride: true, ask });

    expect(ask.mock.calls).toEqual([[`${bound.message} Move anyway?`], [LIFT_QUESTION]]);
    expect(move.mock.calls[1]).toEqual([{ override: true, liftBinding: true }]);
  });

  it('moves anyway without lifting on a second no', async () => {
    const move = refusedUnlessOverridden(bound);
    const ask = vi.fn((question: string) => question !== LIFT_QUESTION);

    await moveOrAsk(move, { canOverride: true, ask });

    expect(move.mock.calls[1]).toEqual([{ override: true, liftBinding: false }]);
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
      throw bound;
    });

    await expect(moveOrAsk(move, { canOverride: false, ask })).rejects.toBe(bound);
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
    expect(isOverridable(other)).toBe(false);
  });
});

describe('giveOrAsk', () => {
  it('asks to give anyway', async () => {
    const give = refusedUnlessOverridden(bound);
    const ask = vi.fn(() => false);

    await expect(giveOrAsk(give, { canOverride: true, ask })).rejects.toBe(bound);
    expect(ask).toHaveBeenCalledWith(`${bound.message} Give anyway?`);
  });
});

describe('bulk moves', () => {
  function result(id: string, problem?: { type: string; detail: string }): BulkResultItem {
    return problem
      ? { entity_id: id, status: 'error', problem: { ...problem, title: 'No', status: 409 } }
      : { entity_id: id, status: 'ok' };
  }
  const refused = (id: string, detail: string) => result(id, { type: 'capacity-exceeded', detail });

  it('finds the entries a GM could move anyway, and only those', () => {
    const results = [
      result('rope'),
      refused('anvil', 'Backpack can carry 20, and this would make it 60.'),
      result('ring', { type: 'item-bound', detail: bound.message }),
      result('map', { type: 'item-not-yours-to-give', detail: 'Not yours.' }),
    ];
    expect(overridableIds(results)).toEqual(['anvil', 'ring']);
  });

  it('asks once for one', () => {
    const results = [refused('anvil', 'Backpack can carry 20, and this would make it 60.')];
    expect(bulkMoveAnywayQuestion(results)).toBe(
      'Backpack can carry 20, and this would make it 60. Move anyway?',
    );
  });

  it('asks once for several', () => {
    const results = [
      refused('anvil', 'Backpack can carry 20, and this would make it 60.'),
      result('ring', { type: 'item-bound', detail: bound.message }),
    ];
    expect(bulkMoveAnywayQuestion(results)).toBe(
      "2 of them can't go there. Backpack can carry 20, and this would make it 60. Move them anyway?",
    );
  });

  it('asks nothing when nothing could be moved anyway', () => {
    expect(bulkMoveAnywayQuestion([result('rope')])).toBeNull();
  });
});
