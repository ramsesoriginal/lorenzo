/**
 * In-process bookkeeping for an in-progress `/give-bulk` flow (ADR 0068) -
 * keyed by a short-lived random token, not the chosen item ids themselves:
 * Discord caps a customId at 100 characters, far too little to embed a
 * handful of full item-instance UUIDs directly (mirrors why `/link`'s own
 * `pending-links.ts` exists - state that has to survive between two
 * separate interactions, but is short-lived enough not to need a DB
 * table). Same in-memory-Map shape as `pending-links.ts`: a lost in-flight
 * selection on restart just means the caller re-runs `/give-bulk`.
 */

export type PendingBulkGive = Readonly<{
  discordUserId: string;
  itemEntityIds: readonly string[];
}>;

type PendingBulkGiveEntry = PendingBulkGive & Readonly<{ expiresAt: number }>;

// Short - this only needs to survive the few seconds between picking items
// and picking a target in the same interactive message, not a real wait
// like /link's OAuth round-trip.
const TTL_MS = 5 * 60 * 1000;

const pendingBulkGives = new Map<string, PendingBulkGiveEntry>();

/** Records a freshly-chosen item set under a fresh token, returning it. */
export function storePendingBulkGive(entry: PendingBulkGive): string {
  const token = crypto.randomUUID();
  pendingBulkGives.set(token, { ...entry, expiresAt: Date.now() + TTL_MS });
  return token;
}

/** Looks up and removes the pending selection for `token` - one-shot, same
 * replay-safety reasoning as `consumePendingLink`. Returns `undefined` if
 * `token` is unknown or its TTL has already elapsed. */
export function consumePendingBulkGive(token: string): PendingBulkGive | undefined {
  const entry = pendingBulkGives.get(token);
  if (!entry) return undefined;
  pendingBulkGives.delete(token);
  if (entry.expiresAt < Date.now()) return undefined;

  const { expiresAt: _expiresAt, ...rest } = entry;
  return rest;
}

export function clearPendingBulkGivesForTests(): void {
  pendingBulkGives.clear();
}
