// Pure, dependency-free helpers shared across pages - no api.ts/auth.ts
// import chain, which pulls in @authgear/web's browser-only side effects
// on import and would break these under a plain Vitest/Node environment
// for no real reason.
import type { CharacterSummaryOut, MeOut, Notification, RosterEntry } from './types';

export function localesToText(locales: string[]): string {
  return locales.join(', ');
}

export function textToLocales(text: string): string[] {
  return text
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

// "" means the user cleared a nullable text field - ProfileUpdate needs an
// explicit null for that (an empty string would fail nickname's own
// min_length=1, and is meaningless for the others too).
export function textOrNull(value: string): string | null {
  return value.trim() === '' ? null : value;
}

export function countUnread(notifications: Notification[]): number {
  return notifications.filter((n) => n.read_at === null).length;
}

// RFC 0017's own fallback chain, shared by every roster-derived display
// (GM revoke list, player-handoff picker, campaign roster view) so all
// three degrade the same way for a user with no nickname/display_name.
export function displayNameFor(entry: {
  display_name: string | null;
  nickname: string | null;
  user_id: string;
}): string {
  return entry.display_name ?? entry.nickname ?? entry.user_id;
}

// RFC 0017 (a) "while here" upgrade: GmOut/PlayerSummaryOut only carry a
// raw user_id (ADR 0076/0079's own accepted limitation at the time) - the
// tenant roster fetch this RFC already needs is a materially better name
// source, resolved by matching user_id against whichever roster entry
// (of any kind) happens to carry it.
export function resolveDisplayName(roster: RosterEntry[], userId: string): string {
  const entry = roster.find((r) => r.user_id === userId);
  return entry ? displayNameFor(entry) : userId;
}

export type CampaignRole = 'gm' | 'player' | 'visible';

// A campaign appearing in a tenant's GET /campaigns list doesn't mean the
// caller personally plays or GMs it - a tenant orga (or a fellow
// participant, for non-secret campaigns) sees the whole catalog. This
// cross-references MeOut's own player/GM grants to say which is which,
// rather than the server repeating "your role here" on every campaign row.
export function campaignRoleFor(campaignId: string, me: MeOut): CampaignRole {
  if (me.campaign_gm_grants.some((c) => c.id === campaignId)) return 'gm';
  if (me.players.some((p) => p.campaign_id === campaignId)) return 'player';
  return 'visible';
}

// RFC 0014's roster-reuse sub-slice: which of the caller's own characters,
// already played in some *other* campaign in this same tenant, could be
// brought into the given campaign instead of creating a new one. A
// character can appear under more than one PlayerContextOut (roster reuse
// is already a thing, ADR 0025) - deduped by entity_id.
export function reusableCharactersFor(
  me: MeOut,
  tenantId: string,
  excludeCampaignId: string,
): CharacterSummaryOut[] {
  const byId = new Map<string, CharacterSummaryOut>();
  for (const player of me.players) {
    if (player.tenant_id !== tenantId || player.campaign_id === excludeCampaignId) continue;
    for (const character of player.characters) {
      byId.set(character.entity_id, character);
    }
  }
  return [...byId.values()];
}
