// /campaigns (ADR 0179): two sections over what GET /me and GET /me/managed already say, for
// libraries only. Where you play: your own seats, with the campaign's name and the one fact "Stop
// using here" needs (who owns each of your characters). Where you run: the campaigns you GM, and
// every campaign of a library you administer, with who is at each table.

import { onCacheRefreshed } from '../../lib/cache';
import { isEditingIn } from '../../lib/editing';
import { runRows, seatsIn } from '../../lib/campaigns';
import { byName } from '../../lib/format';
import { getManaged, getMe } from '../../lib/me';
import { loadSeatOwners } from '../../lib/seatOwners';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import { canCreateTenants } from '../../lib/tenantKind';
import { listMyTenants, listTenantCampaigns } from '../../lib/tenants';
import { renderRunCampaign } from '../RunCampaign/renderer';
import { renderSeat } from '../Seat/renderer';

const required = requiredIn('Campaigns panel');

// `root` is the <CampaignsPanel /> block. It is built, and shown, once; the first load's failure
// rejects, for the page to show. A change anywhere in it builds it again.
export async function renderCampaignsPanel(root: HTMLElement): Promise<void> {
  const error = required<HTMLElement>(root, '[data-error]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const setup = required<HTMLElement>(root, '[data-setup]');
  const play = required<HTMLElement>(root, '[data-play]');
  const playList = required<HTMLElement>(root, '[data-play-list]');
  const run = required<HTMLElement>(root, '[data-run]');
  const runList = required<HTMLElement>(root, '[data-run-list]');

  // Only the newest load paints.
  let latest = 0;

  async function load(): Promise<void> {
    const turn = ++latest;
    const [me, tenants, managed] = await Promise.all([
      getMe(),
      listMyTenants('play'),
      getManaged(),
    ]);
    const libraryNames = new Map(tenants.items.map((tenant) => [tenant.id, tenant.name]));

    // Where you play: the campaign behind each seat, and who owns your characters in its library.
    const seats = seatsIn(me, new Set(libraryNames.keys()));
    const tenantIds = [...new Set(seats.map((seat) => seat.tenant_id))];
    // Where you run: the campaigns you GM, and every campaign of a library you administer, with who
    // is at each table.
    const runRequests = Promise.all(
      runRows(managed).map(async (row) => {
        const element = cloneRoot(root, '[data-run-template]');

        await renderRunCampaign(element, row, me.id);

        return element;
      }),
    );

    // All of it at once: none of these waits for another.
    const [campaignEntries, ownerEntries, runElements] = await Promise.all([
      Promise.all(
        tenantIds.map(async (id) => [id, (await listTenantCampaigns(id)).items] as const),
      ),
      Promise.all(tenantIds.map(async (id) => [id, await loadSeatOwners(id, me)] as const)),
      runRequests,
    ]);
    const campaignsByTenant = new Map(campaignEntries);
    const ownersByTenant = new Map(ownerEntries);
    const seatRows = seats.flatMap((seat) => {
      const campaign = campaignsByTenant.get(seat.tenant_id)?.find((c) => c.id === seat.campaign_id);
      const libraryName = libraryNames.get(seat.tenant_id);

      return campaign && libraryName ? [{ seat, campaign, libraryName }] : [];
    });

    seatRows.sort(
      (a, b) => byName(a.libraryName, b.libraryName) || byName(a.campaign.name, b.campaign.name),
    );

    const seatElements = seatRows.map(({ seat, campaign, libraryName }) => {
      const element = cloneRoot(root, '[data-seat-template]');

      renderSeat(element, {
        campaign,
        libraryName,
        player: seat,
        me,
        owners: ownersByTenant.get(seat.tenant_id) ?? new Map(),
        onChanged: () => void reload(),
      });

      return element;
    });

    if (turn !== latest) return;

    error.hidden = true;
    play.hidden = seatElements.length === 0;
    playList.replaceChildren(...seatElements);
    run.hidden = runElements.length === 0;
    runList.replaceChildren(...runElements);

    // Nothing yet: an account that may create is pointed at /setup (ADR 0180).
    setup.hidden = !canCreateTenants(me);
    empty.hidden = seatElements.length + runElements.length > 0;
  }

  // After a change: the same again, with what it failed on said in place.
  async function reload(): Promise<void> {
    try {
      await load();
    } catch (cause) {
      sayError(error, cause);
    }
  }

  // What was shown came from the cache, and the API has something different.
  onCacheRefreshed(() => {
    if (!isEditingIn(root)) void reload();
  });

  await load();
  root.hidden = false;
}
