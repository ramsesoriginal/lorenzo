// What /campaigns shows and where (ADR 0179), as plain functions over what
// `GET /me`, `GET /me/managed` and the people lists return. Dependency-free
// like format.ts, so a test can hold the sorting and the sentences to what the
// page promises.
//
// Two sections: where you PLAY (a seat of your own, with your characters) and
// where you RUN (a campaign you GM, or one of a library you administer). A
// campaign you do both in is in both.
import { displayNameFor } from './format';
import type { CampaignSummaryOut, ManagedScopeOut, MeOut, PlayerContextOut } from './types';

export type RunRole = 'gm' | 'admin';

export interface RunRow {
  tenantId: string;
  tenantName: string;
  campaignId: string;
  campaignName: string;
  // `gm`: you hold the GM grant. `admin`: you administer the library and so run
  // every campaign in it, GM of it or not (ADR 0086's `is_gm`).
  role: RunRole;
}

export function runRoleLabel(role: RunRole): 'GM' | 'Admin' {
  return role === 'gm' ? 'GM' : 'Admin';
}

function byName(a: string, b: string): number {
  return a.localeCompare(b, 'en', { sensitivity: 'base' });
}

// The campaigns you run, from `GET /me/managed`, libraries only (a repository
// has no campaigns and nobody plays in it, ADR 0178), by library then campaign
// name so the page reads the same on every load.
export function runRows(managed: ManagedScopeOut): RunRow[] {
  const rows: RunRow[] = [];
  for (const tenant of managed.tenants) {
    if (tenant.kind === 'repository') continue;
    for (const campaign of tenant.campaigns) {
      rows.push({
        tenantId: tenant.tenant_id,
        tenantName: tenant.name,
        campaignId: campaign.campaign_id,
        campaignName: campaign.name,
        role: campaign.is_gm ? 'gm' : 'admin',
      });
    }
  }
  return rows.sort(
    (a, b) => byName(a.tenantName, b.tenantName) || byName(a.campaignName, b.campaignName),
  );
}

// Your own seats, in the libraries the page lists: `me.players` spans every
// kind of tenant, and a seat in anything else is not shown.
export function seatsIn(
  me: Pick<MeOut, 'players'>,
  libraryIds: ReadonlySet<string>,
): PlayerContextOut[] {
  return me.players.filter((player) => libraryIds.has(player.tenant_id));
}

// One campaign of yours, once, for the home page: every way you are in it (you can play and run
// the same one) and, if you play, which characters.
export interface TableCard {
  tenantId: string;
  libraryName: string;
  campaignId: string;
  name: string;
  gameSystem: string | null;
  secret: boolean;
  roles: ('Player' | 'GM' | 'Admin')[];
  // Your characters there, or null when you don't play in it.
  characters: string[] | null;
}

// `seats` are your own (seatsIn), `rows` what you run (runRows), `campaigns` every campaign of
// the libraries they are in, by id. A seat whose campaign or library isn't known is left out,
// as /campaigns leaves it out.
export function tableCards(input: {
  seats: readonly PlayerContextOut[];
  rows: readonly RunRow[];
  libraries: ReadonlyMap<string, string>;
  campaigns: ReadonlyMap<string, CampaignSummaryOut>;
}): TableCard[] {
  const cards = new Map<string, TableCard>();

  function cardFor(tenantId: string, libraryName: string, campaignId: string, name: string) {
    let card = cards.get(campaignId);

    if (!card) {
      const campaign = input.campaigns.get(campaignId);

      card = {
        tenantId,
        libraryName,
        campaignId,
        name: campaign?.name ?? name,
        gameSystem: campaign?.game_system ?? null,
        secret: campaign?.secret ?? false,
        roles: [],
        characters: null,
      };
      cards.set(campaignId, card);
    }

    return card;
  }

  for (const seat of input.seats) {
    const campaign = input.campaigns.get(seat.campaign_id);
    const libraryName = input.libraries.get(seat.tenant_id);

    if (!campaign || !libraryName) continue;

    const card = cardFor(seat.tenant_id, libraryName, seat.campaign_id, campaign.name);

    if (!card.roles.includes('Player')) card.roles.push('Player');
    card.characters = [...(card.characters ?? []), ...seat.characters.map((c) => c.name)];
  }

  for (const row of input.rows) {
    const card = cardFor(row.tenantId, row.tenantName, row.campaignId, row.campaignName);
    const role = runRoleLabel(row.role);

    if (!card.roles.includes(role)) card.roles.push(role);
  }

  return [...cards.values()].sort(
    (a, b) => byName(a.libraryName, b.libraryName) || byName(a.name, b.name),
  );
}

// A player's characters on one line, for a GM looking down a roster.
export function charactersLine(characters: readonly { name: string }[]): string {
  return characters.length === 0
    ? 'no character yet'
    : characters.map((character) => character.name).join(', ');
}

// Who a person in a campaign list is: their display name, else nickname, else
// the user id (RFC 0017's fallback chain), and "you" for the signed-in person,
// who is the one name they do not need spelling out.
export function personLabel(
  person: { display_name: string | null; nickname: string | null; user_id: string },
  meId: string,
): string {
  const name = displayNameFor(person);
  return person.user_id === meId ? `${name} (you)` : name;
}
