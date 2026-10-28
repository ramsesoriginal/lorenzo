// What the editor has done to a Map, so it can be undone and done again (ADR 0353). Kept in the
// page's memory and gone when the page is left. A step is the placements one action changed, each
// with what it was before and what it became; none is the entry not being on the Map.

export type PlacementState = {
  geometry: unknown;
  role: string | null;
  style: unknown;
  z: number;
};

export type Change = { entry: string; before: PlacementState | null; after: PlacementState | null };

export type Step = Change[];

export type History = {
  /** A new action: what could be redone is forgotten. */
  record(step: Step): void;
  /** The step to undo, or null; the caller writes each change's `before` back. */
  undo(): Step | null;
  /** The step to redo, or null; the caller writes each change's `after`. */
  redo(): Step | null;
  canUndo(): boolean;
  canRedo(): boolean;
  clear(): void;
};

export const HISTORY_LIMIT = 50;

export function createHistory(limit: number = HISTORY_LIMIT): History {
  const steps: Step[] = [];
  let at = 0;

  return {
    record(step) {
      if (step.length === 0) return;
      steps.length = at;
      steps.push(step);
      if (steps.length > limit) steps.shift();
      at = steps.length;
    },
    undo() {
      if (at === 0) return null;
      at -= 1;
      return steps[at] ?? null;
    },
    redo() {
      if (at >= steps.length) return null;
      const step = steps[at] ?? null;
      at += 1;
      return step;
    },
    canUndo: () => at > 0,
    canRedo: () => at < steps.length,
    clear() {
      steps.length = 0;
      at = 0;
    },
  };
}

/** The write that puts one change back (`before`) or does it again (`after`). */
export function writeFor(
  change: Change,
  direction: 'undo' | 'redo',
): { put: { entry_id: string } & PlacementState } | { remove: string } {
  const state = direction === 'undo' ? change.before : change.after;
  return state ? { put: { entry_id: change.entry, ...state } } : { remove: change.entry };
}
