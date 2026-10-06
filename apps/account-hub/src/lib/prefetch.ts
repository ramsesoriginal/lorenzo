// Warming the cache (lib/cache.ts) for a page while the pointer is still on its link, so the data
// is there, or on its way, when the page asks. Astro's own prefetch fetches the page; this fetches
// what the page then fetches. Every call is a cached read, so what is already held is not asked
// for again, and a failure is the page's to show later, not this.

import { runRows } from './campaigns';
import { readLibrary } from './libraryData';
import { getManaged, getMe } from './me';
import { listNotifications } from './notifications';
import { loadSeatOwners } from './seatOwners';
import { isRepository } from './tenantKind';
import {
  getTenant,
  listCampaignGms,
  listCampaignPlayers,
  listMyTenants,
  listTenantCampaigns,
  listTenantRoster,
} from './tenants';
import type { MeOut, TenantSummaryOut } from './types';

// One library or repository, as opening it asks for it.
async function warmTenant(tenant: TenantSummaryOut, me: MeOut): Promise<void> {
  if (isRepository(tenant)) {
    await Promise.all([getTenant(tenant.id), tenant.role === 'owner' ? listTenantRoster(tenant.id) : null]);

    return;
  }

  await readLibrary(tenant, me);
}

// What each page reads first, keyed by pathname with its trailing slash. `params` is the link's
// query, for the pages that open something particular.
const WARMERS: Record<string, (params: URLSearchParams) => Promise<unknown>> = {
  '/': () => getMe(),
  '/profile/': () => getMe(),
  '/setup/': () => getMe(),
  '/notifications/': () => listNotifications(false),
  '/tenants/': async (params) => {
    const [me, tenants] = await Promise.all([getMe(), listMyTenants()]);
    const wanted = params.get('tenant');
    const tenant = tenants.items.find((t) => t.slug === wanted || t.id === wanted);

    if (tenant) await warmTenant(tenant, me);
  },
  '/campaigns/': async () => {
    const [me, tenants, managed] = await Promise.all([
      getMe(),
      listMyTenants('play'),
      getManaged(),
    ]);
    const seatLibraries = new Set(me.players.map((player) => player.tenant_id));

    await Promise.all([
      // Where you play: the campaigns of each library you have a seat in, and who owns your characters.
      ...tenants.items
        .filter((tenant) => seatLibraries.has(tenant.id))
        .map((tenant) =>
          Promise.all([listTenantCampaigns(tenant.id), loadSeatOwners(tenant.id, me)]),
        ),
      // Where you run: who is at each table.
      ...runRows(managed).map((row) =>
        Promise.all([
          listCampaignPlayers(row.tenantId, row.campaignId),
          listCampaignGms(row.tenantId, row.campaignId),
        ]),
      ),
    ]);
  },
  '/beings/': async () => {
    const [, tenants] = await Promise.all([getMe(), listMyTenants()]);

    await Promise.all(
      tenants.items.filter((t) => !isRepository(t)).map((t) => listTenantCampaigns(t.id)),
    );
  },
};

// How long the pointer rests on a link before it counts as going there.
const HOVER_DELAY_MS = 65;

function warm(link: HTMLAnchorElement): void {
  if (link.origin !== window.location.origin) return;

  // Where the link already is, nothing is asked for: but another library on this very page is not
  // where it is.
  if (`${link.pathname}${link.search}` === `${window.location.pathname}${window.location.search}`) {
    return;
  }

  const path = link.pathname.endsWith('/') ? link.pathname : `${link.pathname}/`;

  WARMERS[path]?.(link.searchParams)?.catch(() => {
    // Not this one's to report.
  });
}

// For someone who is signed in. Any link on the page counts: the header's, the tree's, and the ones
// in a page.
export function bindPrefetch(): void {
  let timer: ReturnType<typeof setTimeout> | undefined;

  function linkIn(event: Event): HTMLAnchorElement | null {
    const target = event.target;

    return target instanceof Element ? target.closest<HTMLAnchorElement>('a[href]') : null;
  }

  document.addEventListener('mouseover', (event) => {
    const link = linkIn(event);

    clearTimeout(timer);

    if (link) timer = setTimeout(() => warm(link), HOVER_DELAY_MS);
  });
  document.addEventListener('mouseout', () => clearTimeout(timer));

  // Keyboard and touch have no hover: arriving at a link, or touching it, is the earliest sign.
  document.addEventListener('focusin', (event) => {
    const link = linkIn(event);

    if (link) warm(link);
  });
  document.addEventListener(
    'touchstart',
    (event) => {
      const link = linkIn(event);

      if (link) warm(link);
    },
    { passive: true },
  );
}
