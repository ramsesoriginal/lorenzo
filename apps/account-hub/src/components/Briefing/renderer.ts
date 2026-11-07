// The home page of someone who belongs somewhere. Each section asks for what it needs and shows
// itself when it has it, so a slow or failed answer holds up or hides only its own section.

import { type RunRow, runRows, seatsIn, type TableCard, tableCards } from '../../lib/campaigns';
import { listMyChanges } from '../../lib/changes';
import { RECENT_KEY } from '../../lib/config';
import {
  linkTasks,
  needsYou,
  orderTasks,
  parseRecent,
  playerTasks,
  splitTables,
  type Task,
  updateTasks,
} from '../../lib/home';
import { listInvites } from '../../lib/invites';
import { getManaged } from '../../lib/me';
import { listLibraryRepositories } from '../../lib/repositories';
import { sayError } from '../../lib/statusLine';
import { studioHref } from '../../lib/studio';
import { requiredIn } from '../../lib/template';
import { listTenantInvites } from '../../lib/tenantInvites';
import { canCreateTenants, isRepository, publishedLabel } from '../../lib/tenantKind';
import { getTenant, listActivityLog, listMyTenants, listTenantCampaigns } from '../../lib/tenants';
import type { InviteOut, ManagedScopeOut, MeOut, TenantSummaryOut } from '../../lib/types';
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

// What waits for a library's administrators and the people who run its campaigns, from what each may
// read: an update announced for a repository the library copied, a link about to end, a new player.
// A read that is refused or fails gives no tasks, never an error: Home only says what it knows.
async function loadTasks(
  tenants: TenantSummaryOut[],
  rows: RunRow[],
  now: number,
): Promise<Task[][]> {
  const none = (): InviteOut[] => [];
  const libraries = tenants.filter((tenant) => !isRepository(tenant));
  const admins = libraries.filter((tenant) => tenant.role === 'owner' || tenant.role === 'orga');

  const updates = admins.map(async (library) =>
    updateTasks(library, await listLibraryRepositories(library.id).catch(() => [])),
  );
  const libraryLinks = libraries
    .filter((tenant) => tenant.role === 'owner')
    .map(async (library) =>
      linkTasks(
        { label: library.name, slug: library.slug },
        await listTenantInvites(library.id).catch(none),
        now,
      ),
    );
  const campaignLinks = rows.map(async (row) =>
    linkTasks(
      { label: row.campaignName, slug: row.tenantSlug },
      await listInvites(row.tenantId, row.campaignId).catch(none),
      now,
    ),
  );
  const players = admins
    .filter((library) => rows.some((row) => row.tenantId === library.id))
    .map(async (library) =>
      playerTasks(
        (await listActivityLog(library.id).catch(() => null))?.items ?? [],
        new Map(
          rows
            .filter((row) => row.tenantId === library.id)
            .map((row) => [row.campaignId, { name: row.campaignName, slug: row.tenantSlug }]),
        ),
        now,
      ),
    );

  const settled = await Promise.all([
    Promise.all(updates),
    Promise.all([...libraryLinks, ...campaignLinks]),
    Promise.all(players),
  ]);

  return settled.map((group) => group.flat());
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
  const repositories = tenants.then((page) => loadRepositories(page.items));

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
      showRepositories(root, await repositories);
    }),
    section('[data-needs]', async () => {
      const [tenantPage, managedScope, drafts] = await Promise.all([
        tenants,
        managed,
        repositories,
      ]);
      const [updates, links, players] = await loadTasks(
        tenantPage.items,
        runRows(managedScope),
        Date.now(),
      );

      showNeeds(
        root,
        orderTasks(updates ?? [], links ?? [], players ?? [], needsYou(drafts, studioHref)),
      );
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
