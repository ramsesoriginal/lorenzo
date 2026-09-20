import { client, unwrap } from './api';

// GM-gating convention established in apps/loot-bot (isCampaignGm): a
// client-side convenience check only, to decide whether to show GM-only
// affordances - the real authorization boundary is each write's own
// server-side check, cross-tenant imprecision and all (campaign_gm_grants
// carries no tenant_id).
export async function isCampaignGm(): Promise<boolean> {
  const me = await unwrap(await client.GET('/me'));
  return me.campaign_gm_grants.length > 0;
}
