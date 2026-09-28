// A GM's "Move anyway" and "Give anyway" (ADR 0128, 0129): a write the API refuses
// because it doesn't fit, or because something is bound, can be sent again with
// `override` by a GM, after asking - and for a binding, with `liftBinding` too, after
// asking again. Everyone else just sees the API's own message.
import { LorenzoApiError } from './api';
import type { AnywayFlags } from './items';
import type { BulkResultItem } from './types';

const BOUND = 'item-bound';
const OVERRIDABLE = new Set(['capacity-exceeded', BOUND]);

export const LIFT_QUESTION = "Lift its binding too, so it won't bind again?";

/** A write the API refused because it doesn't fit or something is bound. */
export function isOverridable(error: unknown): error is LorenzoApiError {
  return error instanceof LorenzoApiError && OVERRIDABLE.has(error.problemType ?? '');
}

export function anywayQuestion(detail: string, verb: 'Move' | 'Give' = 'Move'): string {
  return `${detail} ${verb} anyway?`;
}

export type MoveAnywayOptions = Readonly<{
  /** Whether the viewer is a GM, who may override. */
  canOverride: boolean;
  /** Asks a yes/no question - window.confirm on the page. */
  ask: (question: string) => boolean;
}>;

/**
 * Runs `write`; if it's refused as overridable and the viewer may override, asks, and
 * on a yes runs it again with override - asking first, for a binding, whether to lift
 * it too. Any other failure, or a no, is thrown as it was. Resolves to what the write
 * that went through resolved to - where a move ended up, say (ADR 0133).
 */
export async function writeOrAsk<T>(
  write: (flags: AnywayFlags) => Promise<T>,
  { canOverride, ask }: MoveAnywayOptions,
  verb: 'Move' | 'Give' = 'Move',
): Promise<T> {
  try {
    return await write({});
  } catch (error) {
    if (!canOverride || !isOverridable(error) || !ask(anywayQuestion(error.message, verb))) {
      throw error;
    }
    const liftBinding = error.problemType === BOUND && ask(LIFT_QUESTION);
    return await write({ override: true, liftBinding });
  }
}

export function moveOrAsk<T>(
  move: (flags: AnywayFlags) => Promise<T>,
  options: MoveAnywayOptions,
): Promise<T> {
  return writeOrAsk(move, options, 'Move');
}

export function giveOrAsk<T>(
  give: (flags: AnywayFlags) => Promise<T>,
  options: MoveAnywayOptions,
): Promise<T> {
  return writeOrAsk(give, options, 'Give');
}

function overridable(results: readonly BulkResultItem[]): BulkResultItem[] {
  return results.filter(
    (result) => result.status === 'error' && OVERRIDABLE.has(result.problem?.type ?? ''),
  );
}

/** A bulk move's entries a GM could move anyway, by entity id. */
export function overridableIds(results: readonly BulkResultItem[]): string[] {
  return overridable(results).map((result) => result.entity_id);
}

/** Asked once for every entry of a bulk move a GM could move anyway. */
export function bulkMoveAnywayQuestion(results: readonly BulkResultItem[]): string | null {
  const refused = overridable(results);
  if (refused.length === 0) return null;
  const first = refused[0]?.problem?.detail ?? "That can't go there.";
  if (refused.length === 1) return anywayQuestion(first);
  return `${refused.length} of them can't go there. ${first} Move them anyway?`;
}
