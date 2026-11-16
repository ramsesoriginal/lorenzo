// Personal access tokens (ADR 0269): connecting a device with the code it shows, and the list of
// the tokens a person has made. Pure and dependency-free like inviteLink.ts; the calls to apps/api
// are in personalTokensApi.ts.
import { ApiError } from './apiError';
import { relativeTime } from './relativeTime';
import type { PersonalTokenOut } from './types';

// --- The code ---------------------------------------------------------------

// What apps/api hands out (ADR 0268): eight consonants, shown as ABCD-EFGH.
const CODE_ALPHABET = 'BCDFGHJKMNPQRSTVWXYZ';
const CODE_LENGTH = 8;

// What a person typed, as a code the API will look up: any case, with or without the dash or
// spaces. null for anything that cannot be one.
export function normalizeUserCode(text: string): string | null {
  const letters = text.toUpperCase().replace(/[\s-]+/g, '');

  if (letters.length !== CODE_LENGTH) return null;
  if ([...letters].some((letter) => !CODE_ALPHABET.includes(letter))) return null;

  return `${letters.slice(0, 4)}-${letters.slice(4)}`;
}

// The code in the address (`/device?code=ABCD-EFGH`), if it is one.
export function codeFromSearch(search: string): string | null {
  const code = new URLSearchParams(search).get('code');

  return code === null ? null : normalizeUserCode(code);
}

export const CODE_NOT_FOUND =
  "That code isn't waiting for approval: it may have run out (they last ten minutes) or been typed wrong. Start the connection again on your device.";

// --- Expiry -----------------------------------------------------------------

const DAY_MS = 24 * 60 * 60 * 1000;

// No expiry unless the person sets one (ADR 0268), so "Never" is the first and the default.
export const TOKEN_EXPIRY_PRESETS = [
  { id: 'never', label: 'Never', ms: null },
  { id: '30d', label: 'In 30 days', ms: 30 * DAY_MS },
  { id: '90d', label: 'In 90 days', ms: 90 * DAY_MS },
  { id: '1y', label: 'In a year', ms: 365 * DAY_MS },
] as const;

export type TokenExpiryId = (typeof TOKEN_EXPIRY_PRESETS)[number]['id'];

// The moment a token should stop working, or null for one that never does.
export function tokenExpiryFor(id: string, now: Date): string | null {
  const preset = TOKEN_EXPIRY_PRESETS.find((candidate) => candidate.id === id);

  if (preset === undefined) throw new Error(`Unknown expiry: ${id}`);

  return preset.ms === null ? null : new Date(now.getTime() + preset.ms).toISOString();
}

// --- The list ---------------------------------------------------------------

// The name the device suggested, or a plain one, trimmed and no longer than the API takes.
export function suggestedTokenName(clientName: string | null | undefined): string {
  const name = (clientName ?? '').trim().slice(0, 80);

  return name === '' ? 'My device' : name;
}

export const TOKEN_NAME_MAX = 80;

// Why a token's name cannot be used, in words, or null when it can (ADR 0418, PT5).
export function tokenNameProblem(name: string): string | null {
  const trimmed = name.trim();

  if (trimmed === '') return 'Give the token a name, so you can tell it from the others.';
  if ([...trimmed].length > TOKEN_NAME_MAX) {
    return `A name can be at most ${TOKEN_NAME_MAX} characters.`;
  }

  return null;
}

export function revokeTokenConfirmation(name: string): string {
  return `Revoke "${name}"? Whatever is using it stops working at once, and you can't undo this. You can connect it again with a new code.`;
}

export function tokenState(token: PersonalTokenOut): 'active' | 'expired' {
  return token.is_expired ? 'expired' : 'active';
}

// "Never used", or "Last used" and when; formatted by the caller (it needs the clock).
export function neverUsed(token: PersonalTokenOut): boolean {
  return token.last_used_at === null || token.last_used_at === undefined;
}

// A 404 on a code is the ordinary "no such request" (typed wrong, run out).
export function isCodeNotFound(cause: unknown): boolean {
  return cause instanceof ApiError && cause.status === 404;
}

// --- What a row says ---------------------------------------------------------

/** A token not used for this long is called out, since it may be forgotten (ADR 0418, PT4). */
export const STALE_DAYS = 90;

export type TokenTone = 'ok' | 'never' | 'stale' | 'expired';

export type TokenDescription = {
  /** When it was last used, in words: "Last used today", "Not used for 120 days", "Never used". */
  used: string;
  /** What else matters, in words: when it ends, that it ended, or what to do about a stale one. */
  note: string;
  tone: TokenTone;
  /** An id in the brand's icons.svg without the `icon-` prefix, shown beside the words. */
  icon: string;
};

/**
 * The state of a token in words, an icon and a tone, never colour alone: tinted when it has not been
 * used for a long time, struck through when it has ended (ADR 0418, PT4). Pure; `now` is a parameter.
 */
export function describeToken(token: PersonalTokenOut, now: Date): TokenDescription {
  const day = 24 * 60 * 60 * 1000;
  const never = neverUsed(token);
  const usedAt = never ? null : new Date(token.last_used_at ?? '').getTime();
  const daysSince = usedAt === null ? 0 : Math.floor((now.getTime() - usedAt) / day);
  const expired = tokenState(token) === 'expired';
  const stale = !never && daysSince >= STALE_DAYS;

  let used: string;

  if (never) used = 'Never used';
  else if (stale) used = `Not used for ${daysSince} days`;
  else if (now.getTime() - (usedAt ?? 0) < day) used = 'Last used today';
  else used = `Last used ${relativeTime(token.last_used_at ?? '', now)}`;

  const ends = token.expires_at ? relativeTime(token.expires_at, now) : null;

  if (expired) {
    return { used, note: `Expired ${ends ?? 'earlier'}`, tone: 'expired', icon: 'warning' };
  }
  if (stale) {
    const keeps = 'It still works. Revoke it if you no longer need it.';

    return {
      used,
      note: ends ? `Expires ${ends}. ${keeps}` : keeps,
      tone: 'stale',
      icon: 'kind-clock-unknown',
    };
  }
  if (never) {
    const made = `Made ${relativeTime(token.created_at, now)}`;

    return {
      used,
      note: ends ? `${made}. Expires ${ends}` : made,
      tone: 'never',
      icon: 'kind-clock-unknown',
    };
  }

  return {
    used,
    note: ends ? `Expires ${ends}` : 'Never expires',
    tone: 'ok',
    icon: 'select-item',
  };
}
