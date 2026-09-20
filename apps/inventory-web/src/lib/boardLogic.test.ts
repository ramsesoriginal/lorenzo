import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createUndoController,
  failedEntityIds,
  findMergeCandidates,
  planGive,
  samePrototypes,
  summarizeBulkResults,
  type UndoActions,
} from './boardLogic';
import type { BulkResultItem, ItemInstance } from './types';

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
    prototype_ids: ['proto-sword'],
    container_entity_id: null,
    owner_entity_id: null,
    slug: null,
    ...overrides,
  };
}

function makeBulkResult(overrides: Partial<BulkResultItem> = {}): BulkResultItem {
  return {
    entity_id: 'item-1',
    status: 'ok',
    item_instance: { entity_id: 'item-1' },
    problem: null,
    ...overrides,
  };
}

describe('planGive', () => {
  it('gives the whole stack when no quantity is requested', () => {
    expect(planGive({ quantity: 5 }, undefined)).toEqual({ mode: 'whole' });
  });

  it('gives the whole stack when requested quantity equals the full stack', () => {
    expect(planGive({ quantity: 5 }, 5)).toEqual({ mode: 'whole' });
  });

  it('gives the whole stack when the item has no quantity at all (unstacked)', () => {
    expect(planGive({ quantity: null }, 3)).toEqual({ mode: 'whole' });
  });

  it('gives the whole stack when requested quantity is 0', () => {
    expect(planGive({ quantity: 5 }, 0)).toEqual({ mode: 'whole' });
  });

  it('splits off part of the stack when requested quantity is less than the full stack', () => {
    expect(planGive({ quantity: 5 }, 2)).toEqual({ mode: 'partial', quantity: 2 });
  });

  it('gives the whole stack rather than erroring when requested quantity exceeds the stack', () => {
    // Over-requesting isn't this function's job to reject - the split
    // endpoint itself validates and 422s; planGive only decides *which*
    // call to make.
    expect(planGive({ quantity: 5 }, 9)).toEqual({ mode: 'whole' });
  });
});

describe('summarizeBulkResults', () => {
  it('reports every item succeeded', () => {
    const results = [makeBulkResult(), makeBulkResult({ entity_id: 'item-2' })];
    expect(summarizeBulkResults(results)).toEqual({
      succeededCount: 2,
      failedCount: 0,
      allFailed: false,
    });
  });

  it('reports a partial failure', () => {
    const results = [
      makeBulkResult(),
      makeBulkResult({ entity_id: 'item-2', status: 'error', item_instance: null }),
    ];
    expect(summarizeBulkResults(results)).toEqual({
      succeededCount: 1,
      failedCount: 1,
      allFailed: false,
    });
  });

  it('reports a total failure as allFailed', () => {
    const results = [
      makeBulkResult({ status: 'error', item_instance: null }),
      makeBulkResult({ entity_id: 'item-2', status: 'error', item_instance: null }),
    ];
    expect(summarizeBulkResults(results)).toEqual({
      succeededCount: 0,
      failedCount: 2,
      allFailed: true,
    });
  });

  it('does not report allFailed for an empty result set', () => {
    expect(summarizeBulkResults([]).allFailed).toBe(false);
  });
});

describe('failedEntityIds', () => {
  it('extracts only the failed entries', () => {
    const results = [
      makeBulkResult({ entity_id: 'ok-1' }),
      makeBulkResult({ entity_id: 'bad-1', status: 'error', item_instance: null }),
      makeBulkResult({ entity_id: 'ok-2' }),
      makeBulkResult({ entity_id: 'bad-2', status: 'error', item_instance: null }),
    ];
    expect(failedEntityIds(results)).toEqual(new Set(['bad-1', 'bad-2']));
  });

  it('returns an empty set when nothing failed', () => {
    expect(failedEntityIds([makeBulkResult()])).toEqual(new Set());
  });
});

describe('samePrototypes', () => {
  it('matches identical sets regardless of order', () => {
    expect(samePrototypes(['a', 'b'], ['b', 'a'])).toBe(true);
  });

  it('matches two empty sets', () => {
    expect(samePrototypes([], [])).toBe(true);
  });

  it('rejects different lengths', () => {
    expect(samePrototypes(['a'], ['a', 'b'])).toBe(false);
  });

  it('rejects same length, different members', () => {
    expect(samePrototypes(['a', 'b'], ['a', 'c'])).toBe(false);
  });
});

describe('findMergeCandidates', () => {
  it('finds another stack with the same title and prototype set', () => {
    const target = makeItem({ entity_id: 'a', title: 'Arrow', prototype_ids: ['proto-arrow'] });
    const candidate = makeItem({ entity_id: 'b', title: 'Arrow', prototype_ids: ['proto-arrow'] });
    expect(findMergeCandidates([target, candidate], target)).toEqual([candidate]);
  });

  it('excludes the target itself', () => {
    const target = makeItem({ entity_id: 'a' });
    expect(findMergeCandidates([target], target)).toEqual([]);
  });

  it('excludes items with a matching title but a different prototype set', () => {
    // Regression guard for the exact bug this filter exists to prevent:
    // ADR 0067's title-fallback-to-name means two unrelated catalog items
    // can display an identical title.
    const target = makeItem({
      entity_id: 'a',
      title: 'Ring',
      prototype_ids: ['proto-ring-of-fire'],
    });
    const lookalike = makeItem({
      entity_id: 'b',
      title: 'Ring',
      prototype_ids: ['proto-ring-of-frost'],
    });
    expect(findMergeCandidates([target, lookalike], target)).toEqual([]);
  });

  it('excludes items with a different title even if prototypes overlap', () => {
    const target = makeItem({ entity_id: 'a', title: 'Arrow', prototype_ids: ['proto-arrow'] });
    const other = makeItem({ entity_id: 'b', title: 'Bolt', prototype_ids: ['proto-arrow'] });
    expect(findMergeCandidates([target, other], target)).toEqual([]);
  });
});

describe('createUndoController', () => {
  let actions: { [K in keyof UndoActions]: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    vi.useFakeTimers();
    actions = {
      setOwner: vi.fn().mockResolvedValue(undefined),
      unsetOwner: vi.fn().mockResolvedValue(undefined),
      setContainer: vi.fn().mockResolvedValue(undefined),
      clearContainer: vi.fn().mockResolvedValue(undefined),
      splitItemInstance: vi.fn().mockResolvedValue(undefined),
      mergeItemInstance: vi.fn().mockResolvedValue(undefined),
    };
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('has nothing pending before anything is recorded', () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    expect(controller.getPending()).toBeNull();
  });

  it('restore-owner: calls setOwner when there was a previous owner', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record(
      { kind: 'restore-owner', entityId: 'item-1', previousOwnerId: 'char-1' },
      vi.fn(),
    );
    await controller.apply();
    expect(actions.setOwner).toHaveBeenCalledWith('tenant-1', 'item-1', 'char-1');
    expect(actions.unsetOwner).not.toHaveBeenCalled();
  });

  it('restore-owner: calls unsetOwner when there was no previous owner', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record(
      { kind: 'restore-owner', entityId: 'item-1', previousOwnerId: null },
      vi.fn(),
    );
    await controller.apply();
    expect(actions.unsetOwner).toHaveBeenCalledWith('tenant-1', 'item-1');
    expect(actions.setOwner).not.toHaveBeenCalled();
  });

  it('restore-container: calls setContainer when there was a previous container', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record(
      { kind: 'restore-container', entityId: 'item-1', previousContainerId: 'box-1' },
      vi.fn(),
    );
    await controller.apply();
    expect(actions.setContainer).toHaveBeenCalledWith('tenant-1', 'item-1', 'box-1');
  });

  it('restore-container: calls clearContainer when there was no previous container', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record(
      { kind: 'restore-container', entityId: 'item-1', previousContainerId: null },
      vi.fn(),
    );
    await controller.apply();
    expect(actions.clearContainer).toHaveBeenCalledWith('tenant-1', 'item-1');
  });

  it('undo-merge: re-splits an equivalent stack off the surviving instance', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record(
      { kind: 'undo-merge', intoEntityId: 'item-2', quantity: 3, previousOwnerId: 'char-1' },
      vi.fn(),
    );
    await controller.apply();
    expect(actions.splitItemInstance).toHaveBeenCalledWith('tenant-1', 'item-2', 3, 'char-1');
  });

  it('undo-merge: omits owner when the merged-away instance had none', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record(
      { kind: 'undo-merge', intoEntityId: 'item-2', quantity: 3, previousOwnerId: null },
      vi.fn(),
    );
    await controller.apply();
    expect(actions.splitItemInstance).toHaveBeenCalledWith('tenant-1', 'item-2', 3, undefined);
  });

  it('undo-split: merges the split-off instance back into the source', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record(
      { kind: 'undo-split', splitOffEntityId: 'item-3', intoEntityId: 'item-1' },
      vi.fn(),
    );
    await controller.apply();
    expect(actions.mergeItemInstance).toHaveBeenCalledWith('tenant-1', 'item-3', 'item-1');
  });

  it('is a no-op to apply when nothing is pending', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    await controller.apply();
    expect(actions.setOwner).not.toHaveBeenCalled();
    expect(actions.mergeItemInstance).not.toHaveBeenCalled();
  });

  it('is one-slot: a new record overwrites whatever was pending, not a stack', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record({ kind: 'restore-owner', entityId: 'item-1', previousOwnerId: 'a' }, vi.fn());
    controller.record({ kind: 'restore-owner', entityId: 'item-2', previousOwnerId: 'b' }, vi.fn());
    await controller.apply();
    expect(actions.setOwner).toHaveBeenCalledTimes(1);
    expect(actions.setOwner).toHaveBeenCalledWith('tenant-1', 'item-2', 'b');
  });

  it('clears the pending state once applied, so a second apply is a no-op', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record({ kind: 'restore-owner', entityId: 'item-1', previousOwnerId: 'a' }, vi.fn());
    await controller.apply();
    await controller.apply();
    expect(actions.setOwner).toHaveBeenCalledTimes(1);
  });

  it('clear() drops the pending action without applying it', async () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record({ kind: 'restore-owner', entityId: 'item-1', previousOwnerId: 'a' }, vi.fn());
    controller.clear();
    expect(controller.getPending()).toBeNull();
    await controller.apply();
    expect(actions.setOwner).not.toHaveBeenCalled();
  });

  it('expires after the TTL and calls onExpire, dropping the pending action', () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions, 1000);
    const onExpire = vi.fn();
    controller.record(
      { kind: 'restore-owner', entityId: 'item-1', previousOwnerId: 'a' },
      onExpire,
    );
    expect(controller.getPending()).not.toBeNull();
    vi.advanceTimersByTime(999);
    expect(onExpire).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onExpire).toHaveBeenCalledTimes(1);
    expect(controller.getPending()).toBeNull();
  });

  it('a fresh record resets the expiry timer of the previous one', () => {
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions, 1000);
    const firstExpire = vi.fn();
    const secondExpire = vi.fn();
    controller.record(
      { kind: 'restore-owner', entityId: 'item-1', previousOwnerId: 'a' },
      firstExpire,
    );
    vi.advanceTimersByTime(600);
    controller.record(
      { kind: 'restore-owner', entityId: 'item-2', previousOwnerId: 'b' },
      secondExpire,
    );
    vi.advanceTimersByTime(600);
    // 1200ms have passed since the first record, but only 600ms since the
    // second - the first timer must not have fired independently.
    expect(firstExpire).not.toHaveBeenCalled();
    expect(secondExpire).not.toHaveBeenCalled();
    vi.advanceTimersByTime(400);
    expect(secondExpire).toHaveBeenCalledTimes(1);
  });

  it('propagates a failed action so the caller can decide how to surface it', async () => {
    actions.setOwner.mockRejectedValueOnce(new Error('boom'));
    const controller = createUndoController('tenant-1', actions as unknown as UndoActions);
    controller.record({ kind: 'restore-owner', entityId: 'item-1', previousOwnerId: 'a' }, vi.fn());
    await expect(controller.apply()).rejects.toThrow('boom');
    // Still consumed, matching the original inline implementation - a
    // failed undo isn't retried automatically.
    expect(controller.getPending()).toBeNull();
  });
});
