/**
 * In-process bookkeeping for account-linking flows in progress, keyed by
 * the OAuth `state` value - deliberately an in-memory Map, not a DB table
 * (ADR 0029): this is a single-process bot, the data is short-lived (a few
 * minutes at most), and a lost in-flight attempt on restart just means the
 * user re-runs `/link`. Not exported as a class/singleton object - like
 * config.ts, this module's own top-level state *is* the singleton.
 */

export type PendingLink = Readonly<{
  discordUserId: string;
  codeVerifier: string;
}>;

type PendingLinkEntry = PendingLink & Readonly<{ expiresAt: number }>;

// 10 minutes, per ADR 0029.
const TTL_MS = 10 * 60 * 1000;

const pendingLinks = new Map<string, PendingLinkEntry>();

/** Records a freshly-started `/link` flow under its `state` value. */
export function storePendingLink(state: string, link: PendingLink): void {
  pendingLinks.set(state, { ...link, expiresAt: Date.now() + TTL_MS });
}

/**
 * Looks up and removes the pending flow for `state` - one-shot, so a given
 * `state` can only ever be redeemed once whether or not the lookup
 * succeeds, which is what makes replaying a captured callback URL harmless.
 * Returns `undefined` if `state` is unknown or the entry's TTL has already
 * elapsed (a lookup-time check is sufficient here - see ADR 0029; an
 * abandoned entry just sits harmlessly until either redeemed-and-rejected
 * or the process restarts).
 */
export function consumePendingLink(state: string): PendingLink | undefined {
  const entry = pendingLinks.get(state);
  if (!entry) return undefined;
  pendingLinks.delete(state);
  if (entry.expiresAt < Date.now()) return undefined;

  const { expiresAt: _expiresAt, ...link } = entry;
  return link;
}

export function clearPendingLinksForTests(): void {
  pendingLinks.clear();
}
