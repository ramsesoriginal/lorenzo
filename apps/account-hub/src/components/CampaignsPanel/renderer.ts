// /campaigns (ADR 0179): two sections over what GET /me and GET /me/managed already say, for
// libraries only. Where you play: your own seats, with the campaign's name and the one fact "Stop
// using here" needs (who owns each of your characters). Where you run: the campaigns you GM, and
// every campaign of a library you administer, with who is at each table.

import { runRows, seatsIn } from '../../lib/campaigns';
import { byName } from '../../lib/format';
import { getManaged, getMe } from '../../lib/me';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import { canCreateTenants } from '../../lib/tenantKind';
import { listMyTenants, listTenantCampaigns } from '../../lib/tenants';
import { renderRunCampaign } from '../RunCampaign/renderer';
import { loadSeatOwners } from '../Seat/owners';
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
    const me = await getMe();
    const [tenants, managed] = await Promise.all([listMyTenants('play'), getManaged()]);
    const libraryNames = new Map(tenants.items.map((tenant) => [tenant.id, tenant.name]));

    // Where you play: the campaign behind each seat, and who owns your characters in its library.
    const seats = seatsIn(me, new Set(libraryNames.keys()));
    const tenantIds = [...new Set(seats.map((seat) => seat.tenant_id))];
    const campaignsByTenant = new Map(
      await Promise.all(
        tenantIds.map(async (id) => [id, (await listTenantCampaigns(id)).items] as const),
      ),
    );
    const ownersByTenant = new Map(
      await Promise.all(tenantIds.map(async (id) => [id, await loadSeatOwners(id, me)] as const)),
    );
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

    // Where you run: the campaigns you GM, and every campaign of a library you administer, with who
    // is at each table.
    const runElements = await Promise.all(
      runRows(managed).map(async (row) => {
        const element = cloneRoot(root, '[data-run-template]');

        await renderRunCampaign(element, row, me.id);

        return element;
      }),
    );

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

  await load();
  root.hidden = false;
}
