import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import type { CampaignSummary } from './types';

const fetchMe = async () => unwrap(await client.GET('/me'));
let me: ReturnType<typeof fetchMe> | undefined;

// Fetched once per page: the GM check, the seats and the viewer's locales all read it. A failed
// request isn't kept, so the next caller tries again.
export function getMe() {
  me ??= fetchMe().catch((e: unknown) => {
    me = undefined;
    throw e;
  });
  return me;
}

/** The campaigns of this library, as the viewer may list them. */
export async function listCampaigns(tenantId: string): Promise<CampaignSummary[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/campaigns', {
        params: { path: { tenant_id: tenantId }, query: { page, size: MAX_PAGE_SIZE } },
      }),
    ),
  );
}

// GM-gating convention established in apps/loot-bot (isCampaignGm): a client-side convenience check
// only, to decide whether to show GM-only affordances - the real authorization boundary is each
// write's own server-side check. campaign_gm_grants carries no tenant_id, so a grant counts only if
// its campaign is one of this library's: a GM elsewhere is a player here.
export async function gmCampaignsIn(tenantId: string): Promise<CampaignSummary[]> {
  const grants = new Set((await getMe()).campaign_gm_grants.map((campaign) => campaign.id));
  if (grants.size === 0) return [];
  return (await listCampaigns(tenantId)).filter((campaign) => grants.has(campaign.id));
}

export async function isCampaignGm(tenantId: string): Promise<boolean> {
  return (await gmCampaignsIn(tenantId)).length > 0;
}

/** Whether the viewer holds a membership in the library (an Owner or an Organizer). */
export async function isTenantMember(tenantId: string): Promise<boolean> {
  return (await getMe()).memberships.some((membership) => membership.tenant_id === tenantId);
}

/** The viewer's own user id. */
export async function viewerId(): Promise<string> {
  return (await getMe()).id;
}

/** The languages on the viewer's profile, else the browser's (ADR 0108). */
export async function viewerLocales(): Promise<string[]> {
  const locales = await getMe().then(
    (m) => m.locales,
    () => [],
  );
  return locales.length > 0 ? locales : [...navigator.languages];
}

/** The viewer's own seats in a library: one per campaign they play in. */
export async function seatsIn(tenantId: string) {
  return (await getMe()).players.filter((seat) => seat.tenant_id === tenantId);
}

/** The beings the viewer plays in this library (their seats' characters), by entity id. */
export async function myBeingIds(tenantId: string): Promise<Set<string>> {
  const seats = await seatsIn(tenantId);
  return new Set(seats.flatMap((seat) => seat.characters.map((character) => character.entity_id)));
}
