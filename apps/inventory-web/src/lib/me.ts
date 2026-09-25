import { client, unwrap } from './api';

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
// server-side check, cross-tenant imprecision and all (campaign_gm_grants
// carries no tenant_id).
export async function isCampaignGm(): Promise<boolean> {
  return (await getMe()).campaign_gm_grants.length > 0;
}

/** The languages on the viewer's profile, else the browser's (ADR 0108). */
export async function viewerLocales(): Promise<string[]> {
  const locales = await getMe().then(
    (m) => m.locales,
    () => [],
  );
  return locales.length > 0 ? locales : [...navigator.languages];
}
