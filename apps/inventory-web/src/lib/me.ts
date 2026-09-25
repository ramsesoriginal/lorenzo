import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';

const fetchMe = async () => unwrap(await client.GET('/me'));
let me: ReturnType<typeof fetchMe> | undefined;

// Fetched once per page: the GM check and the viewer's locales both read it.
// A failed request isn't kept, so the next caller tries again.
function getMe() {
  me ??= fetchMe().catch((e: unknown) => {
    me = undefined;
    throw e;
  });
  return me;
}

// GM-gating convention established in apps/loot-bot (isCampaignGm): a
// client-side convenience check only, to decide whether to show GM-only
// affordances - the real authorization boundary is each write's own
// server-side check. campaign_gm_grants carries no tenant_id, so a grant
// counts only if its campaign is one of this tenant's: a GM elsewhere is a
// player here.
export async function isCampaignGm(tenantId: string): Promise<boolean> {
  const grants = new Set((await getMe()).campaign_gm_grants.map((campaign) => campaign.id));
  if (grants.size === 0) return false;
  const campaigns = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/campaigns', {
        params: { path: { tenant_id: tenantId }, query: { page, size: MAX_PAGE_SIZE } },
      }),
    ),
  );
  return campaigns.some((campaign) => grants.has(campaign.id));
}

/**
 * Whether the viewer holds a membership in the tenant (an owner or orga). The catalog and
 * the being search need one (ADR 0032, 0078); a player has a seat in a campaign instead.
 */
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
