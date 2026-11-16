// The home page of someone who belongs somewhere. Each section asks for what it needs and shows
// itself when it has it, so a slow or failed answer holds up or hides only its own section.

import { getAppLinks } from '@lorenzo/api-client';
import { type RunRow, runRows, seatsIn, type TableCard, tableCards } from '../../lib/campaigns';
import { listMyChanges } from '../../lib/changes';
import { API_BASE_URL, RECENT_KEY } from '../../lib/config';
import {
  homeSubtitle,
  linkTasks,
  needsYou,
  orderTasks,
  parseRecent,
  playerTasks,
  type RepositoryFacts,
  runItems,
  splitTables,
  type Task,
  updateTasks,
} from '../../lib/home';
import { listInvites } from '../../lib/invites';
import { getManaged } from '../../lib/me';
import { listLibraryRepositories } from '../../lib/repositories';
import { currentShell } from '../../lib/shell';
import { sayError } from '../../lib/statusLine';
import { roleLabel, STUDIO_NEW_HREF, studioHref } from '../../lib/studio';
import { requiredIn } from '../../lib/template';
import { listTenantInvites } from '../../lib/tenantInvites';
import { canCreateTenants, isRepository, publishedLabel } from '../../lib/tenantKind';
import {
  getTenant,
  listActivityLog,
  listMyTenants,
  listTenantCampaigns,
  listTenantRoster,
} from '../../lib/tenants';
import type { InviteOut, ManagedScopeOut, MeOut, TenantSummaryOut } from '../../lib/types';
import { showApps } from './apps';
import { showChanges } from './changes';
import { showNeeds } from './needs';
import { type PlaySeat, showPlay } from './play';
import { showRecent } from './recent';
import { showRun } from './run';

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
function loadRepositories(tenants: TenantSummaryOut[]): Promise<RepositoryFacts[]> {
  return Promise.all(
    tenants.filter(isRepository).map(async (tenant) => ({
      name: tenant.name,
      slug: tenant.slug,
      role: roleLabel(tenant.role),
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
      { label: row.campaignName, slug: row.tenantSlug, place: row.tenantName },
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
            .map((row) => [
              row.campaignId,
              { name: row.campaignName, slug: row.tenantSlug, place: row.tenantName },
            ]),
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

  required<HTMLElement>(root, '[data-subtitle]').textContent = name ?? '';
  root.hidden = false;

  const tenants = listMyTenants();
  const managed = getManaged();
  const changes = listMyChanges(CHANGES_SHOWN);
  const repositories = tenants.then((page) => loadRepositories(page.items));
  const mayCreate = canCreateTenants(me);

  // A section whose answer fails says so in its own place and leaves the rest alone.
  async function section(selector: string, work: () => Promise<void>): Promise<void> {
    try {
      await work();
    } catch (cause) {
      const element = required<HTMLElement>(root, selector);
      const error = required<HTMLElement>(element, '[data-error]');

      element.hidden = false;
      sayError(error, cause);
    }
  }

  const characterNames = new Map(
    me.players.flatMap((player) => player.characters).map((c) => [c.entity_id, c.name]),
  );

  showRecent(root, parseRecent(window.localStorage.getItem(RECENT_KEY)));
  void getAppLinks(API_BASE_URL).then(
    (registry) => showApps(root, registry),
    () => {},
  );

  // What waits for the person, which the subtitle counts and the status bar says, and which libraries
  // have an update announced, which "What you run" says beside them.
  const needs = (async () => {
    const [tenantPage, managedScope, drafts] = await Promise.all([tenants, managed, repositories]);
    const [updates, links, players] = await loadTasks(
      tenantPage.items,
      runRows(managedScope),
      Date.now(),
    );
    const tasks = orderTasks(
      updates ?? [],
      links ?? [],
      players ?? [],
      needsYou(drafts, studioHref),
    );

    return { tasks, waiting: new Set((updates ?? []).map((task) => task.id.split(':')[1] ?? '')) };
  })();

  await Promise.all([
    section('[data-play]', async () => {
      const [tenantPage, managedScope] = await Promise.all([tenants, managed]);
      const cards = splitTables(await loadTables(me, tenantPage.items, managedScope)).play;
      const seats: PlaySeat[] = cards.flatMap((card) => {
        const seat = me.players.find((player) => player.campaign_id === card.campaignId);

        return seat ? [{ card, playerId: seat.id }] : [];
      });

      showPlay(root, seats, () => void renderBriefing(root, me));
    }),
    section('[data-run]', async () => {
      const [tenantPage, managedScope, facts, { waiting }] = await Promise.all([
        tenants,
        managed,
        repositories,
        needs,
      ]);
      const rows = runRows(managedScope);
      const libraries = tenantPage.items
        .filter((tenant) => !isRepository(tenant))
        .map((tenant) => ({
          id: tenant.id,
          name: tenant.name,
          slug: tenant.slug,
          role: tenant.role,
          admin: tenant.role === 'owner' || tenant.role === 'orga',
        }));
      const looked = libraries.filter(
        (library) =>
          ['owner', 'orga', 'author'].includes(library.role) ||
          rows.some((row) => row.tenantId === library.id),
      );
      const counts = async (read: (id: string) => Promise<{ total: number }>, ids: string[]) =>
        new Map(
          (
            await Promise.all(
              ids.map(
                async (id) =>
                  [
                    id,
                    await read(id).then(
                      (page) => page.total,
                      () => undefined,
                    ),
                  ] as const,
              ),
            )
          ).flatMap(([id, total]) => (total === undefined ? [] : [[id, total] as const])),
        );
      const [campaignCounts, peopleCounts] = await Promise.all([
        counts(
          listTenantCampaigns,
          looked.map((library) => library.id),
        ),
        counts(
          listTenantRoster,
          looked.filter((library) => library.admin).map((library) => library.id),
        ),
      ]);

      showRun(
        root,
        runItems({
          libraries: looked,
          rows,
          campaignCounts,
          peopleCounts,
          updatesWaiting: waiting,
          repositories: facts,
          repositoryHref: studioHref,
          roleText: roleLabel,
        }),
        { createLibrary: mayCreate, createRepository: mayCreate },
      );
      required<HTMLAnchorElement>(root, '[data-new-repository]').href = STUDIO_NEW_HREF;
    }),
    section('[data-needs]', async () => {
      const { tasks } = await needs;

      showNeeds(root, tasks);
      required<HTMLElement>(root, '[data-subtitle]').textContent = homeSubtitle(
        name ?? null,
        tasks.length,
      );
      currentShell()?.statusBar({ meta: tasks.length > 0 ? `${tasks.length} need you` : null });
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
