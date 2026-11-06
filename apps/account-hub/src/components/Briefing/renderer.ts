// The home page of someone who belongs somewhere. Each section asks for what it needs and shows
// itself when it has it, so a slow or failed answer holds up or hides only its own section.

import { runRows, seatsIn, type TableCard, tableCards } from '../../lib/campaigns';
import { listMyChanges } from '../../lib/changes';
import { RECENT_KEY } from '../../lib/config';
import { needsYou, parseRecent, splitTables } from '../../lib/home';
import { getManaged } from '../../lib/me';
import { sayError } from '../../lib/statusLine';
import { studioHref } from '../../lib/studio';
import { requiredIn } from '../../lib/template';
import { canCreateTenants, isRepository, publishedLabel } from '../../lib/tenantKind';
import { getTenant, listMyTenants, listTenantCampaigns } from '../../lib/tenants';
import type { ManagedScopeOut, MeOut, TenantSummaryOut } from '../../lib/types';
import { showChanges } from './changes';
import { showNeeds } from './needs';
import { showRecent } from './recent';
import { type RepositoryCard, showRepositories } from './repositories';
import { showTables } from './tables';

const CHANGES_SHOWN = 5;

const required = requiredIn('Briefing');

// What you play and run, as one card for each campaign. Names come from each library's own
// campaign list, which is also where a campaign's game system is.
async function loadTables(
  me: MeOut,
  tenants: TenantSummaryOut[],
  managed: ManagedScopeOut,
): Promise<TableCard[]> {
  const libraries = new Map(
    tenants
      .filter((tenant) => !isRepository(tenant))
      .map((tenant) => [tenant.id, { name: tenant.name, slug: tenant.slug }]),
  );
  const seats = seatsIn(me, new Set(libraries.keys()));
  const rows = runRows(managed);
  const tenantIds = new Set([...seats.map((s) => s.tenant_id), ...rows.map((r) => r.tenantId)]);
  const lists = await Promise.all([...tenantIds].map((id) => listTenantCampaigns(id)));
  const campaigns = new Map(lists.flatMap((page) => page.items).map((c) => [c.id, c]));

  return tableCards({ seats, rows, libraries, campaigns });
}

// A repository's published state isn't in the list, only in its own read (ADR 0118); where that
// can't be read, the card goes without it.
function loadRepositories(tenants: TenantSummaryOut[]): Promise<RepositoryCard[]> {
  return Promise.all(
    tenants.filter(isRepository).map(async (tenant) => ({
      name: tenant.name,
      slug: tenant.slug,
      role: tenant.role,
      status: await getTenant(tenant.id).then(
        ({ tenant: detail }) => publishedLabel(detail.published_at),
        () => null,
      ),
    })),
  );
}

export async function renderBriefing(root: HTMLElement, me: MeOut): Promise<void> {
  const name = me.display_name ?? me.nickname;

  required<HTMLElement>(root, '[data-greeting]').textContent = name
    ? `Welcome back, ${name}.`
    : 'Welcome back.';
  root.hidden = false;

  const tenants = listMyTenants();
  const managed = getManaged();
  const changes = listMyChanges(CHANGES_SHOWN);

  // A section whose answer fails says so in its own place and leaves the rest alone.
  function section(selector: string, work: () => Promise<void>): Promise<void> {
    return work().catch((cause) => {
      const element = required<HTMLElement>(root, selector);
      const error = required<HTMLElement>(element, '[data-error]');

      element.hidden = false;
      sayError(error, cause);
    });
  }

  const characterNames = new Map(
    me.players.flatMap((player) => player.characters).map((c) => [c.entity_id, c.name]),
  );

  required<HTMLElement>(root, '[data-setup]').hidden = !canCreateTenants(me);
  showRecent(root, parseRecent(window.localStorage.getItem(RECENT_KEY)));

  await Promise.all([
    section('[data-play]', async () => {
      const [tenantPage, managedScope] = await Promise.all([tenants, managed]);
      const split = splitTables(await loadTables(me, tenantPage.items, managedScope));

      showTables(root, '[data-play]', split.play);
      showTables(root, '[data-run]', split.run);
    }),
    section('[data-repositories]', async () => {
      const repositories = await loadRepositories((await tenants).items);

      showRepositories(root, repositories);
      showNeeds(root, needsYou(repositories, studioHref));
    }),
    section('[data-changes]', async () => {
      // Without the libraries' names, a change just doesn't say which one.
      const [changePage, tenantItems] = await Promise.all([
        changes,
        tenants.then(
          (page) => page.items,
          () => [] as TenantSummaryOut[],
        ),
      ]);
      const libraries = new Map(tenantItems.map((t) => [t.id, t.name]));

      showChanges(root, changePage.items, {
        characterName: (id) => characterNames.get(id) ?? 'your character',
        libraryName: (id) => libraries.get(id) ?? null,
      });
    }),
  ]);
}
