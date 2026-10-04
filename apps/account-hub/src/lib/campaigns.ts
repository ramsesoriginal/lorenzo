// What /campaigns shows and where (ADR 0179), as plain functions over what
// `GET /me`, `GET /me/managed` and the people lists return. Dependency-free
// like format.ts, so a test can hold the sorting and the sentences to what the
// page promises.
//
// Two sections: where you PLAY (a seat of your own, with your characters) and
// where you RUN (a campaign you GM, or one of a library you administer). A
// campaign you do both in is in both.
import { displayNameFor } from './format';
import type { ManagedScopeOut, MeOut, PlayerContextOut } from './types';

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
