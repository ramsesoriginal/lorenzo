// A GM's "Move anyway" (ADR 0128): a move the API refuses for capacity can be
// sent again with `override`, by a GM, after asking. Everyone else just sees
// the API's own message.
import { LorenzoApiError } from './api';
import type { BulkResultItem } from './types';

const OVER_CAPACITY = 'capacity-exceeded';

/** A move the API refused because it wouldn't fit. */
export function isOverCapacity(error: unknown): error is LorenzoApiError {
  return error instanceof LorenzoApiError && error.problemType === OVER_CAPACITY;
}

export function moveAnywayQuestion(detail: string): string {
  return `${detail} Move anyway?`;
}

export type MoveAnywayOptions = Readonly<{
  /** Whether the viewer is a GM, who may override. */
  canOverride: boolean;
  /** Asks a yes/no question - window.confirm on the page. */
  ask: (question: string) => boolean;
}>;

/**
 * Runs `move`; if it's refused for capacity and the viewer may override,
 * asks, and on a yes runs it again with override. Any other failure, or a no,
 * is thrown as it was.
 */
export async function moveOrAsk(
  move: (override: boolean) => Promise<void>,
  { canOverride, ask }: MoveAnywayOptions,
): Promise<void> {
  try {
    await move(false);
  } catch (error) {
    if (!canOverride || !isOverCapacity(error) || !ask(moveAnywayQuestion(error.message))) {
      throw error;
    }
    await move(true);
  }
}

/** A bulk move's entries refused for capacity, by entity id. */
export function overCapacityIds(results: readonly BulkResultItem[]): string[] {
  return results
    .filter((result) => result.status === 'error' && result.problem?.type === OVER_CAPACITY)
    .map((result) => result.entity_id);
}

/** Asked once for every entry of a bulk move refused for capacity. */
export function bulkMoveAnywayQuestion(results: readonly BulkResultItem[]): string | null {
  const refused = results.filter(
    (result) => result.status === 'error' && result.problem?.type === OVER_CAPACITY,
  );
  if (refused.length === 0) return null;
  const first = refused[0]?.problem?.detail ?? "That doesn't fit.";
  if (refused.length === 1) return moveAnywayQuestion(first);
  return `${refused.length} of them don't fit. ${first} Move them anyway?`;
}
