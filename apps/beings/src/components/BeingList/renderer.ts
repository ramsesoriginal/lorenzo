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
import { getEntityDetail } from '../../lib/entities';
import { beingPageHref } from '../../lib/entityLinks';
import { errorMessage } from '../../lib/errorMessage';
import {
  isListView,
  type ListView,
  mapLimited,
  type Numbers,
  numbersOf,
  rememberView,
  savedView,
  sideRows,
  vitalLine,
} from '../../lib/listViews';
import { gmCampaignsIn, isTenantMember, listCampaigns, seatsIn } from '../../lib/me';
import { createBeing, createOwnCharacter, seatOptions } from '../../lib/people';
import { say } from '../../lib/statusLine';
import { statVocabulary } from '../../lib/statValues';
import { cloneTemplate, requiredIn } from '../../lib/template';
import { renderListPictures } from './pictures';

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
  const pictures = renderListPictures(root, tenantId);
  const side = required<HTMLElement>(root, '[data-side]');
  const viewSwitch = required<HTMLElement>(root, '[data-view-switch]');

  root.hidden = false;
  say(status, 'Loading beings…');

  const [beings, campaigns, gm, member, owned, seats] = await Promise.all([
    listBeings(tenantId),
    listCampaigns(tenantId).catch(() => []),
    gmCampaignsIn(tenantId).then(
      (found) => found.length > 0,
      () => false,
    ),
    isTenantMember(tenantId).catch(() => false),
    // Which are the viewer's own: for the Mine filter and the badge. Without it, none is marked.
    ownedBeingIds(tenantId).catch(() => new Set<string>()),
    seatsIn(tenantId).catch(() => []),
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

  // The view is the person's, kept in this browser (BN1).
  let view: ListView = savedView();
  const viewRadios = [...viewSwitch.querySelectorAll<HTMLInputElement>('input[type="radio"]')];
  for (const radio of viewRadios) radio.checked = radio.value === view;

  // Cards and side by side show numbers: one read of each being, once, at a few at a time.
  const numbers = new Map<string, Numbers | null>();
  let vocabulary: Awaited<ReturnType<typeof statVocabulary>> | undefined;

  async function loadNumbers(shown: readonly ListedBeing[]) {
    vocabulary ??= await statVocabulary(tenantId).catch(() => []);
    const vocabularyNow = vocabulary;

    await mapLimited(
      shown.filter((being) => !numbers.has(being.entity_id)),
      6,
      async (being) => {
        try {
          numbers.set(
            being.entity_id,
            numbersOf(vocabularyNow, await getEntityDetail(tenantId, being.entity_id)),
          );
        } catch {
          // A being whose numbers cannot be read is shown without them.
          numbers.set(being.entity_id, null);
        }
      },
    );
  }

  function drawSide(shown: readonly ListedBeing[]) {
    const found = shown.map((being) => numbers.get(being.entity_id) ?? undefined);
    const table = document.createElement('table');
    const caption = document.createElement('caption');
    const head = document.createElement('tr');
    const body = document.createElement('tbody');
    const corner = document.createElement('th');

    table.className = 'datasheet-table';
    caption.className = 'visually-hidden';
    caption.textContent = 'Numbers of the beings, side by side';
    corner.scope = 'col';
    corner.textContent = 'Number';
    head.append(corner);

    for (const being of shown) {
      const th = document.createElement('th');
      const link = document.createElement('a');
      const kind = document.createElement('span');

      th.scope = 'col';
      link.href = beingPageHref(tenantAddress, being);
      link.textContent = being.name;
      kind.className = 'caption';
      kind.textContent = kindLabel(being);
      th.append(link, kind);
      head.append(th);
    }

    for (const row of sideRows(found)) {
      const tr = document.createElement('tr');
      const th = document.createElement('th');

      th.scope = 'row';
      th.textContent = row.label;
      if (row.derived) {
        const mark = document.createElement('span');

        mark.className = 'caption';
        mark.textContent = ' (derived)';
        th.append(mark);
      }
      tr.append(th);

      for (const being of found) {
        const td = document.createElement('td');

        td.textContent = being?.all.find((n) => n.name === row.name)?.text ?? '—';
        tr.append(td);
      }

      body.append(tr);
    }

    table.append(caption, document.createElement('thead'), body);
    table.tHead?.append(head);
    side.replaceChildren(table);
  }

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

    const vital = numbers.get(being.entity_id)?.vitals[0];
    const vitalNode = required<HTMLElement>(row, '[data-vital]');

    if (view === 'cards' && vital) {
      vitalNode.textContent = vitalLine(vital);
      vitalNode.hidden = false;
    }

    pictures.observe(row, being.entity_id, being.name);
    return row;
  }

  async function draw() {
    const turn = ++latest;
    remember();

    try {
      const filters = await currentFilters();
      const shown = filterBeings(beings, filters);

      if (turn !== latest) return;
      if (view !== 'rows') {
        say(status, 'Loading numbers…');
        await loadNumbers(shown);
        if (turn !== latest) return;
      }

      pictures.reset();
      list.replaceChildren(...shown.map((being) => drawRow(being, ownedIds)));
      list.classList.toggle('being-cards', view === 'cards');
      list.hidden = shown.length === 0 || view === 'side';
      side.hidden = shown.length === 0 || view !== 'side';
      if (view === 'side') drawSide(shown);
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

  for (const radio of viewRadios) {
    radio.addEventListener('change', () => {
      if (!radio.checked || !isListView(radio.value)) return;

      view = radio.value;
      rememberView(view);
      void draw();
    });
  }

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

  // A player may make a character of their own in a campaign they play in; the API still decides.
  if (seats.length > 0) {
    const ownForm = required<HTMLFormElement>(root, '[data-own-form]');
    const seat = required<HTMLSelectElement>(ownForm, '[data-own-seat]');
    const ownName = required<HTMLInputElement>(ownForm, '[data-own-name]');
    const ownCreate = required<HTMLButtonElement>(ownForm, '[data-own-create]');
    const ownStatus = required<HTMLElement>(ownForm, '[data-own-status]');
    const names = new Map(campaigns.map((campaign) => [campaign.id, campaign.name]));

    for (const option of seatOptions(seats, names)) {
      seat.append(new Option(option.label, option.seatId));
    }

    ownForm.hidden = false;

    ownForm.addEventListener('submit', async (event) => {
      event.preventDefault();

      const wanted = ownName.value.trim();

      if (!wanted || !seat.value) return;

      ownCreate.disabled = true;
      say(ownStatus, 'Creating…');

      try {
        const made = await createOwnCharacter(tenantId, wanted, seat.value);

        window.location.assign(beingPageHref(tenantAddress, made));
      } catch (error) {
        say(ownStatus, errorMessage(error), true);
        ownCreate.disabled = false;
      }
    });
  }

  await draw();
}
