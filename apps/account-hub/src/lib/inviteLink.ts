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

// What a person pastes or types into a box: the whole link, or only the code at its end. A
// token has no whitespace in it, so any is dropped: a link wrapped over two lines in a message,
// or a code read out and typed in groups.
export function inviteTokenFrom(pasted: string): string | null {
  const text = pasted.replace(/\s+/g, '');
  const hash = text.lastIndexOf('#');
  return readInviteToken(hash === -1 ? text : text.slice(hash));
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

// A GM link lives at most a week (ADR 0177), against a player link's thirty
// days. The longest preset is six days, not seven, for the same reason the
// player links stop at four weeks: a client clock a little fast must never ask
// for more than the API allows.
export const GM_EXPIRY_PRESETS = [
  { id: '1h', label: '1 hour', ms: HOUR_MS },
  { id: '1d', label: '1 day', ms: DAY_MS },
  { id: '3d', label: '3 days', ms: 3 * DAY_MS },
  { id: '6d', label: '6 days', ms: 6 * DAY_MS },
] as const;

export type GmExpiryPresetId = (typeof GM_EXPIRY_PRESETS)[number]['id'];

export function expiresAtFor(presetId: ExpiryPresetId | GmExpiryPresetId, now: Date): string {
  const preset = [...EXPIRY_PRESETS, ...GM_EXPIRY_PRESETS].find((p) => p.id === presetId);
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

// A GM link is worth more than a player link, and says so (ADR 0177): the first
// person to open it becomes a GM of the campaign, and it works once.
export const GM_LINK_SHOWN_ONCE_NOTICE =
  "This link won't be shown again, and it works once: whoever opens it first becomes a GM of this campaign. Send it only to the person who should run it, or revoke it.";

// What a link makes someone: `player` for every link before ADR 0177, `gm`, and (ADR 0211) an
// `author` or an `orga` of a library or repository. A library-access link makes no one anything.
export type InviteRole = 'player' | 'gm' | 'author' | 'orga';

export type InviteKind = 'campaign' | 'tenant_role' | 'library_access';

export function linkKindLabel(
  role: InviteRole | null,
): 'Player link' | 'GM link' | 'Author link' | 'Organizer link' | 'Library link' {
  switch (role) {
    case 'gm':
      return 'GM link';
    case 'author':
      return 'Author link';
    case 'orga':
      return 'Organizer link';
    case null:
      return 'Library link';
    default:
      return 'Player link';
  }
}

// A role with its article, as a sentence wants it (ADR 0194's names: never `orga`).
const ROLE_PHRASES = {
  player: 'a player',
  gm: 'a GM',
  author: 'an Author',
  orga: 'an Organizer',
} as const satisfies Record<InviteRole, string>;

export function rolePhrase(role: InviteRole): string {
  return ROLE_PHRASES[role];
}

// What the /join page says it offers, and what its button says.
export function inviteOffer(role: InviteRole): { sentence: string; joinLabel: string } {
  return role === 'gm'
    ? {
        sentence: "You've been invited to run this campaign as a GM.",
        joinLabel: 'Join as a GM',
      }
    : {
        sentence: "You've been invited to join this campaign as a player.",
        joinLabel: 'Join',
      };
}

// What GET /invites/{token} says, which is all a visitor knows before they accept.
export interface InvitePreview {
  kind: InviteKind;
  name: string;
  tenant_kind: 'play' | 'repository' | null;
  role: InviteRole | null;
}

function placeWord(tenantKind: InvitePreview['tenant_kind']): 'library' | 'repository' {
  return tenantKind === 'repository' ? 'repository' : 'library';
}

// The sentence under the name, and the button: a campaign link as ever, a role link as an offer of
// a role in a library or repository, a library link as a repository being shared with a library
// of the visitor's (ADR 0211).
export function offerFor(preview: InvitePreview): { sentence: string; actionLabel: string } {
  if (preview.kind === 'library_access') {
    return {
      sentence: `The repository ${preview.name} is being shared with a library of yours. Choose which one, and it is yours to browse and copy.`,
      actionLabel: 'Share',
    };
  }

  if (preview.kind === 'tenant_role' && preview.role !== null) {
    const noun = placeWord(preview.tenant_kind);
    const phrase = rolePhrase(preview.role);

    return {
      sentence: `You've been invited to join the ${noun} ${preview.name} as ${phrase}.`,
      actionLabel: preview.role === 'orga' ? 'Join as an Organizer' : 'Join as an Author',
    };
  }

  const campaign = inviteOffer(preview.role ?? 'player');

  return { sentence: campaign.sentence, actionLabel: campaign.joinLabel };
}

export function joinedMessage(
  campaignName: string,
  alreadyJoined: boolean,
  role: InviteRole = 'player',
): string {
  const noun = role === 'gm' ? 'a GM' : 'a player';
  return alreadyJoined
    ? `You're already ${noun} ${role === 'gm' ? 'of' : 'in'} ${campaignName}.`
    : `You're in. ${campaignName} lists you as ${noun}.`;
}

// What the page says once a link was used (or had already been): `shareTargetName` is the library the
// repository was shared with.
export function joinedMessageFor(
  preview: InvitePreview,
  joined: { already_joined: boolean; role: InviteRole | null },
  shareTargetName = '',
): string {
  if (preview.kind === 'library_access') {
    return joined.already_joined
      ? `${preview.name} is already shared with ${shareTargetName}.`
      : `${preview.name} is now shared with ${shareTargetName}.`;
  }

  if (preview.kind === 'tenant_role') {
    // A link never changes a role someone already has, so it says only that they belong.
    return joined.already_joined
      ? `You already belong to ${preview.name}. A link doesn't change anyone's role.`
      : `You're in. ${preview.name} lists you as ${rolePhrase(joined.role ?? 'author')}.`;
  }

  return joinedMessage(preview.name, joined.already_joined, joined.role ?? 'player');
}

// --- Choosing the library to share with ----------------------------------------------------

export interface ShareTarget {
  id: string;
  name: string;
  // With what it is, for a list that holds both: "Faerûn (repository)".
  label: string;
}

// What a person may share a repository with: the libraries they are an Owner of, and the
// repositories too, since a bridge is built on another (ADR 0211). Any other role is not enough.
export function shareTargets(managed: {
  tenants: readonly {
    tenant_id: string;
    name: string;
    role: 'owner' | 'orga' | 'author' | null;
    kind: 'play' | 'repository';
  }[];
}): ShareTarget[] {
  return managed.tenants
    .filter((tenant) => tenant.role === 'owner')
    .map((tenant) => ({
      id: tenant.tenant_id,
      name: tenant.name,
      label: `${tenant.name} (${placeWord(tenant.kind)})`,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export const NO_SHARE_TARGET_MESSAGE =
  "You aren't an Owner of a library yet, so there is nothing to share this repository with.";

// Pasting what someone sent: the whole link or just its code (the token is the code). Returns
// where to go, or what to say.
export const PASTE_ERROR =
  "That doesn't look like an invite link or code. Check it against what you were sent.";

export function pastedInvite(pasted: string, origin: string): { href: string } | { error: string } {
  const token = inviteTokenFrom(pasted);

  return token === null ? { error: PASTE_ERROR } : { href: inviteUrl(origin, token) };
}

export function revokeConfirmation(): string {
  return 'Revoke this link? Nobody will be able to join with it any more. People who already joined stay.';
}
