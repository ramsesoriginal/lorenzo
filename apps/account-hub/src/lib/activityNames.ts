// Names for the ids in the activity log (RFC 0017 (f)). The log holds raw ids: the actor, the
// target, and ids inside `detail` ("campaign=<id>, player=<id>"). Wherever an id has a slug or a
// person's name, that is shown instead, with the id kept as the tooltip. Pure and dependency-free
// like format.ts.
import type { PlayerSummaryOut, RosterEntry } from './types';

// What a log entry's target is an entity of, so its id can be looked up as one.
const ENTITY_TARGETS = new Set(['item_instance', 'item', 'character', 'group', 'entity']);

// The keys in `detail` whose values are entity ids.
const ENTITY_DETAIL_KEYS = /\b(?:character|source)=([0-9a-f-]{36})\b/gi;

const UUID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;

// Every id the page already knows a name for, without asking anyone. People are by display name,
// else nickname; a tenant, a campaign by slug; a player by the person they are, since that is what
// "player=<id>" means to read. An id with no name is not in it.
export function knownNames(input: {
  tenant: { id: string; slug: string };
  campaigns: readonly { id: string; slug: string }[];
  roster: readonly RosterEntry[] | null;
  players: readonly PlayerSummaryOut[];
}): Map<string, string> {
  const names = new Map<string, string>([[input.tenant.id, input.tenant.slug]]);

  for (const campaign of input.campaigns) names.set(campaign.id, campaign.slug);

  for (const entry of input.roster ?? []) {
    const name = entry.display_name ?? entry.nickname;

    if (name) names.set(entry.user_id, name);
  }

  for (const player of input.players) {
    const name = names.get(player.user_id);

    if (name) names.set(player.id, name);
  }

  return names;
}

// The ids in an entry that name entities (an item, a character, a group), which only a lookup of
// each can name.
export function entityIdsIn(entry: {
  target_type: string;
  target_id: string | null;
  detail: string | null;
}): string[] {
  const ids: string[] = [];

  if (entry.target_id && ENTITY_TARGETS.has(entry.target_type)) ids.push(entry.target_id);

  for (const match of (entry.detail ?? '').matchAll(ENTITY_DETAIL_KEYS)) {
    if (match[1]) ids.push(match[1]);
  }

  return ids;
}

export type Segment = string | { id: string; label: string };

// `text` cut at its ids: what is between stays a string, and an id `labelOf` has a name for becomes
// `{ id, label }`. An id without one stays in the text as it is.
export function segments(text: string, labelOf: (id: string) => string | undefined): Segment[] {
  const parts: Segment[] = [];
  let plain = '';
  let from = 0;

  for (const match of text.matchAll(UUID)) {
    const label = labelOf(match[0]);

    plain += text.slice(from, match.index);
    from = match.index + match[0].length;

    if (label === undefined) {
      plain += match[0];
    } else {
      if (plain) parts.push(plain);
      plain = '';
      parts.push({ id: match[0], label });
    }
  }

  plain += text.slice(from);

  if (plain) parts.push(plain);

  return parts;
}
