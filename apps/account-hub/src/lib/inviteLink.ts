// Pure helpers for campaign invite links (ADR 0171), dependency-free like
// format.ts: how a link is built and read, what an invite's state is called,
// and the one place a token is kept while a person logs in.

// --- The link -------------------------------------------------------------

// The token goes in the fragment: a browser never sends one to a server, a
// proxy, an access log or a Referer (ADR 0092 requirement 7, and why it is not
// a path segment or a query).
export function inviteUrl(origin: string, token: string): string {
  return `${origin}/join/#${token}`;
}

// What apps/api issues is URL-safe base64 of 256 bits (43 characters). Anything
// else in the fragment is not a token, and is not sent anywhere.
const TOKEN_SHAPE = /^[A-Za-z0-9_-]{16,256}$/;

export function readInviteToken(hash: string): string | null {
  const token = hash.startsWith('#') ? hash.slice(1) : hash;
  return TOKEN_SHAPE.test(token) ? token : null;
}

// --- Expiry ---------------------------------------------------------------

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

// Presets, not a date picker: no time zones to get wrong. The longest is four
// weeks, not the API's thirty days, so a client clock that runs a little fast
// never asks for more than the API allows (ADR 0092).
export const EXPIRY_PRESETS = [
  { id: '1h', label: '1 hour', ms: HOUR_MS },
  { id: '1d', label: '1 day', ms: DAY_MS },
  { id: '1w', label: '1 week', ms: 7 * DAY_MS },
  { id: '4w', label: '4 weeks', ms: 28 * DAY_MS },
] as const;

export type ExpiryPresetId = (typeof EXPIRY_PRESETS)[number]['id'];

export function expiresAtFor(presetId: ExpiryPresetId, now: Date): string {
  const preset = EXPIRY_PRESETS.find((p) => p.id === presetId);
  if (preset === undefined) throw new Error(`Unknown expiry: ${presetId}`);
  return new Date(now.getTime() + preset.ms).toISOString();
}

// --- Use limit ------------------------------------------------------------

// The box is optional: empty means no limit (max_uses omitted). Otherwise a
// whole number of at least 1, or null for "not a number I can use".
export function parseMaxUses(text: string): { maxUses: number | null } | null {
  const trimmed = text.trim();
  if (trimmed === '') return { maxUses: null };
  if (!/^\d+$/.test(trimmed)) return null;
  const value = Number(trimmed);
  return Number.isSafeInteger(value) && value >= 1 ? { maxUses: value } : null;
}

// --- What an invite is ------------------------------------------------------

export interface InviteState {
  is_active: boolean;
  revoked_at: string | null;
  expires_at: string;
  max_uses: number | null;
  use_count: number;
}

export type InviteStatus = 'active' | 'revoked' | 'expired' | 'used-up';

// Named by the first reason that applies. The API's own is_active has the last
// word: a link it calls dead is never shown as Active, whatever this clock says.
export function inviteStatus(invite: InviteState, now: Date): InviteStatus {
  if (invite.revoked_at !== null) return 'revoked';
  if (new Date(invite.expires_at).getTime() <= now.getTime()) return 'expired';
  if (invite.max_uses !== null && invite.use_count >= invite.max_uses) return 'used-up';
  return invite.is_active ? 'active' : 'expired';
}

export const STATUS_LABELS: Record<InviteStatus, string> = {
  active: 'Active',
  revoked: 'Revoked',
  expired: 'Expired',
  'used-up': 'Used up',
};

export function usesLabel(invite: Pick<InviteState, 'max_uses' | 'use_count'>): string {
  return invite.max_uses === null
    ? `${invite.use_count}, no limit`
    : `${invite.use_count} of ${invite.max_uses}`;
}

// --- Keeping the token across the login ----------------------------------------

export const INVITE_TOKEN_KEY = 'lorenzo.invite';

// The one place a token is kept: the page's own sessionStorage, for as long as
// a login takes, then removed. Never localStorage, never a cookie, never logged.
// Returns whether it could be kept; storage can be blocked, and a login would
// then lose the link.
export function rememberInviteToken(
  storage: Pick<Storage, 'setItem'> | undefined,
  token: string,
): boolean {
  try {
    if (storage === undefined) return false;
    storage.setItem(INVITE_TOKEN_KEY, token);
    return true;
  } catch {
    return false;
  }
}

export function storedInviteToken(storage: Pick<Storage, 'getItem'> | undefined): string | null {
  try {
    return readInviteToken(storage?.getItem(INVITE_TOKEN_KEY) ?? '');
  } catch {
    return null;
  }
}

export function forgetInviteToken(storage: Pick<Storage, 'removeItem'> | undefined): void {
  try {
    storage?.removeItem(INVITE_TOKEN_KEY);
  } catch {
    // Nothing to forget it from.
  }
}

// --- What is said ---------------------------------------------------------------

// Every dead link answers the same 404 on purpose (ADR 0092): unknown, expired,
// revoked, used up. So there is one sentence, which does not tell them apart.
export const DEAD_LINK_MESSAGE =
  "This link doesn't work any more. Ask whoever sent it for a new one.";

export const LINK_SHOWN_ONCE_NOTICE =
  "This link won't be shown again. Anyone who has it can join this campaign as a player until it expires or you revoke it.";

export function joinedMessage(campaignName: string, alreadyJoined: boolean): string {
  return alreadyJoined
    ? `You're already a player in ${campaignName}.`
    : `You're in. ${campaignName} lists you as a player.`;
}

export function revokeConfirmation(): string {
  return 'Revoke this link? Nobody will be able to join with it any more. People who already joined stay.';
}
