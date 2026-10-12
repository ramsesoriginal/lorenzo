// The beings of a library (ADR 0271): a search, three filters (campaign, kind, mine) and the list,
// with a form to make a new one for those who may. The filters live in the address so a filtered
// list can be shared or come back after Back.

import {
  campaignBeingIds,
  type Filters,
  filterBeings,
  type Kind,
  kindLabel,
  type ListedBeing,
  listBeings,
  ownedBeingIds,
} from '../../lib/beingList';
import { beingPageHref } from '../../lib/entityLinks';
import { errorMessage } from '../../lib/errorMessage';
import { gmCampaignsIn, isTenantMember, listCampaigns } from '../../lib/me';
import { createBeing } from '../../lib/people';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';

export type BeingListOptions = {
  root: HTMLElement;
  /** The library's id, and what its address calls it (an id or a slug). */
  tenantId: string;
  tenantAddress: string;
};

const required = requiredIn('Being list');

const KINDS: readonly Kind[] = ['all', 'character', 'npc'];

export async function renderBeingList(options: BeingListOptions): Promise<void> {
  const { root, tenantId, tenantAddress } = options;
  const search = required<HTMLInputElement>(root, '[data-search]');
  const campaignSelect = required<HTMLSelectElement>(root, '[data-campaign]');
  const kindSelect = required<HTMLSelectElement>(root, '[data-kind]');
  const mine = required<HTMLInputElement>(root, '[data-mine]');
  const status = required<HTMLElement>(root, '[data-status]');
  const list = required<HTMLUListElement>(root, '[data-list]');
  const template = required<HTMLTemplateElement>(root, '[data-being-template]');
  const form = required<HTMLFormElement>(root, '[data-create-form]');

  root.hidden = false;
  say(status, 'Loading beings…');

  const [beings, campaigns, gm, member, owned] = await Promise.all([
    listBeings(tenantId),
    listCampaigns(tenantId).catch(() => []),
    gmCampaignsIn(tenantId).then(
      (found) => found.length > 0,
      () => false,
    ),
    isTenantMember(tenantId).catch(() => false),
    // Which are the viewer's own: for the Mine filter and the badge. Without it, none is marked.
    ownedBeingIds(tenantId).catch(() => new Set<string>()),
  ]);

  // The Campaign filter lists the campaigns the viewer can list; "All" is first.
  campaignSelect.append(new Option('All campaigns', ''));
  for (const campaign of campaigns) campaignSelect.append(new Option(campaign.name, campaign.id));
  campaignSelect.closest('label')?.toggleAttribute('hidden', campaigns.length === 0);

  const ownedIds = owned;
  // A campaign's roster is fetched when first wanted, and kept.
  const rosters = new Map<string, Set<string>>();

  // Reads the address into the controls.
  const params = new URLSearchParams(window.location.search);
  search.value = params.get('q') ?? '';
  const kindParam = params.get('kind') as Kind | null;
  kindSelect.value = kindParam && KINDS.includes(kindParam) ? kindParam : 'all';
  mine.checked = params.get('mine') === '1';
  const campaignParam = params.get('campaign') ?? '';
  campaignSelect.value = campaigns.some((c) => c.id === campaignParam) ? campaignParam : '';

  let latest = 0;

  function remember() {
    const url = new URL(window.location.href);
    const set = (key: string, value: string) =>
      value ? url.searchParams.set(key, value) : url.searchParams.delete(key);

    set('q', search.value.trim());
    set('kind', kindSelect.value === 'all' ? '' : kindSelect.value);
    set('mine', mine.checked ? '1' : '');
    set('campaign', campaignSelect.value);
    window.history.replaceState(window.history.state, '', url);
  }

  async function currentFilters(): Promise<Filters> {
    let campaign: Set<string> | null = null;

    if (campaignSelect.value) {
      const id = campaignSelect.value;
      let roster = rosters.get(id);

      if (!roster) {
        roster = await campaignBeingIds(tenantId, id);
        rosters.set(id, roster);
      }

      campaign = roster;
    }

    return {
      search: search.value,
      kind: kindSelect.value as Kind,
      mine: mine.checked ? ownedIds : null,
      campaign,
    };
  }

  function drawRow(being: ListedBeing, ownedSet: ReadonlySet<string> | null): HTMLLIElement {
    const row = cloneTemplate<HTMLLIElement>(template, 'li');

    required<HTMLAnchorElement>(row, '[data-link]').href = beingPageHref(tenantAddress, being);
    required<HTMLElement>(row, '[data-name]').textContent = being.name;
    required<HTMLElement>(row, '[data-kind-badge]').textContent = kindLabel(being);
    required<HTMLElement>(row, '[data-mine-badge]').hidden = !ownedSet?.has(being.entity_id);

    return row;
  }

  async function draw() {
    const turn = ++latest;
    remember();

    try {
      const filters = await currentFilters();
      const shown = filterBeings(beings, filters);

      if (turn !== latest) return;

      list.replaceChildren(...shown.map((being) => drawRow(being, ownedIds)));
      list.hidden = shown.length === 0;
      say(
        status,
        shown.length === 0
          ? beings.length === 0
            ? 'No beings yet.'
            : 'No beings match.'
          : `${shown.length} ${shown.length === 1 ? 'being' : 'beings'}`,
      );
    } catch (error) {
      if (turn === latest) say(status, errorMessage(error), true);
    }
  }

  let debounce: ReturnType<typeof setTimeout> | undefined;

  search.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => void draw(), 150);
  });

  for (const control of [campaignSelect, kindSelect, mine]) {
    control.addEventListener('change', () => void draw());
  }

  // Making one is for those who run a campaign or the library; the API still decides.
  if (gm || member) {
    form.hidden = false;

    const name = required<HTMLInputElement>(form, '[data-create-name]');
    const create = required<HTMLButtonElement>(form, '[data-create]');
    const createStatus = required<HTMLElement>(form, '[data-create-status]');

    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      const wanted = name.value.trim();

      if (!wanted) return;

      create.disabled = true;
      say(createStatus, 'Creating…');

      try {
        const made = await createBeing(tenantId, wanted);

        window.location.assign(beingPageHref(tenantAddress, made));
      } catch (error) {
        say(createStatus, errorMessage(error), true);
        create.disabled = false;
      }
    });
  }

  await draw();
}
