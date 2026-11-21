// The beings of a library (ADR 0271, BN1, BN4): a search, a kind, a scope (all or mine) and a
// campaign, and the list in three views, with a dialog to make a new one for those who may. The
// filters live in the address so a filtered list can be shared or come back after Back.

import { closeDialog, fadeOnDismiss, openDialog } from '@lorenzo/app-shell';
import { nextValue, UndoStack } from '../../lib/adjust';
import {
  campaignBeingIds,
  type Filters,
  filterBeings,
  type Kind,
  type ListedBeing,
  listBeings,
  ownedBeingIds,
} from '../../lib/beingList';
import { getEntityDetail } from '../../lib/entities';
import { beingPageHref } from '../../lib/entityLinks';
import { errorMessage } from '../../lib/errorMessage';
import {
  columnsOf,
  isListView,
  type ListView,
  mapLimited,
  type Numbers,
  numbersOf,
  rememberView,
  savedView,
} from '../../lib/listViews';
import { gmCampaignsIn, isTenantMember, listCampaigns, seatsIn } from '../../lib/me';
import {
  createBeing,
  createOwnCharacter,
  listCampaignPlayers,
  seatOptions,
} from '../../lib/people';
import { playedByOf } from '../../lib/playedBy';
import { currentShell } from '../../lib/shell';
import { say } from '../../lib/statusLine';
import { clearStat, StatChangedError, setStat, statVocabulary } from '../../lib/statValues';
import { requiredIn } from '../../lib/template';
import { getTenant } from '../../lib/tenants';
import { renderListPictures } from './pictures';
import { type Drawing, drawCards, drawRows, drawSide } from './views';

export type BeingListOptions = {
  root: HTMLElement;
  /** The library's id, and what its address calls it (an id or a slug). */
  tenantId: string;
  tenantAddress: string;
};

const required = requiredIn('Being list');

const KINDS: readonly Kind[] = ['all', 'character', 'npc'];

const radios = (group: HTMLElement) => [
  ...group.querySelectorAll<HTMLInputElement>('input[type="radio"]'),
];

export async function renderBeingList(options: BeingListOptions): Promise<void> {
  const { root, tenantId, tenantAddress } = options;
  const title = required<HTMLElement>(root, '[data-title]');
  const subtitle = required<HTMLElement>(root, '[data-subtitle]');
  const search = required<HTMLInputElement>(root, '[data-search]');
  const kindSwitch = required<HTMLElement>(root, '[data-kind-switch]');
  const scopeSwitch = required<HTMLElement>(root, '[data-scope-switch]');
  const campaignSelect = required<HTMLSelectElement>(root, '[data-campaign]');
  const viewSwitch = required<HTMLElement>(root, '[data-view-switch]');
  const modeSwitch = required<HTMLElement>(root, '[data-list-mode]');
  const undoButton = required<HTMLButtonElement>(root, '[data-list-undo]');
  const status = required<HTMLElement>(root, '[data-status]');
  const list = required<HTMLElement>(root, '[data-list]');
  const side = required<HTMLElement>(root, '[data-side]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const newButton = required<HTMLButtonElement>(root, '[data-new]');
  const newOwnButton = required<HTMLButtonElement>(root, '[data-new-own]');
  const pictures = renderListPictures(root, tenantId);

  root.hidden = false;
  document.querySelector<HTMLElement>('[data-page-title]')?.setAttribute('hidden', '');
  say(status, 'Loading beings…');

  const [beings, campaigns, gm, member, owned, seats, tenant] = await Promise.all([
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
    getTenant(tenantId).catch(() => null),
  ]);

  // The Campaign filter lists the campaigns the viewer can list; "All" is first.
  campaignSelect.append(new Option('All campaigns', ''));
  for (const campaign of campaigns) campaignSelect.append(new Option(campaign.name, campaign.id));
  campaignSelect.closest('label')?.toggleAttribute('hidden', campaigns.length === 0);

  subtitle.textContent = tenant ? `The characters of ${tenant.name}.` : '';

  const ownedIds = owned;
  // A campaign's roster is fetched when first wanted, and kept.
  const rosters = new Map<string, Set<string>>();
  // Who plays what, from the rosters the viewer may read; read in the background.
  let playedBy = new Map<string, string[]>();
  let rostersKnown = false;

  void Promise.all(
    campaigns.map((campaign) => listCampaignPlayers(tenantId, campaign.id).catch(() => null)),
  ).then((found) => {
    const read = found.filter((roster) => roster !== null);

    rostersKnown = read.length > 0;
    playedBy = playedByOf(read);
    void draw();
  });

  // Reads the address into the controls.
  const params = new URLSearchParams(window.location.search);
  search.value = params.get('q') ?? '';
  const kindParam = params.get('kind') as Kind | null;
  const kindValue = kindParam && KINDS.includes(kindParam) ? kindParam : 'all';
  for (const radio of radios(kindSwitch)) radio.checked = radio.value === kindValue;
  const scopeValue = params.get('mine') === '1' ? 'mine' : 'all';
  for (const radio of radios(scopeSwitch)) radio.checked = radio.value === scopeValue;
  const campaignParam = params.get('campaign') ?? '';
  campaignSelect.value = campaigns.some((c) => c.id === campaignParam) ? campaignParam : '';

  // The view is the person's, kept in this browser (BN1).
  let view: ListView = savedView();
  for (const radio of radios(viewSwitch)) radio.checked = radio.value === view;

  const checked = (group: HTMLElement) => radios(group).find((radio) => radio.checked)?.value ?? '';

  // ---- numbers: one read of each being, a few at a time, when a view shows them -----------------

  const numbers = new Map<string, Numbers | null>();
  let vocabulary: Awaited<ReturnType<typeof statVocabulary>> = [];
  let vocabularyLoaded = false;

  async function loadNumbers(shown: readonly ListedBeing[]) {
    if (!vocabularyLoaded) {
      vocabulary = await statVocabulary(tenantId).catch(() => []);
      vocabularyLoaded = true;
    }

    await mapLimited(
      shown.filter((being) => !numbers.has(being.entity_id)),
      6,
      async (being) => {
        try {
          numbers.set(
            being.entity_id,
            numbersOf(vocabulary, await getEntityDetail(tenantId, being.entity_id)),
          );
        } catch {
          // A being whose numbers cannot be read is shown without them.
          numbers.set(being.entity_id, null);
        }
      },
    );
  }

  // ---- Play in side by side (BN8) --------------------------------------------------------------

  let playing = false;
  let busy = false;
  const history = new UndoStack(30);
  let toast: { dismiss(): void } | null = null;

  const canRun = (being: ListedBeing) => gm || member || ownedIds.has(being.entity_id);

  async function reread(being: ListedBeing) {
    numbers.set(
      being.entity_id,
      numbersOf(vocabulary, await getEntityDetail(tenantId, being.entity_id)),
    );
  }

  async function step(being: ListedBeing, name: string, direction: 'step-down' | 'step-up') {
    const number = numbers.get(being.entity_id)?.all.find((candidate) => candidate.name === name);
    const definition = vocabulary.find((entry) => entry.definition.id === number?.id)?.definition;

    if (!number || !definition || number.value === null || busy) return;

    const before = number.value;
    const after = nextValue(before, direction, 1, number.floor);

    if (after === before) {
      say(status, `${number.label} of ${being.name} cannot go further.`);
      return;
    }

    busy = true;

    try {
      await setStat(tenantId, being.entity_id, definition, after, {
        value: before,
        own: number.own,
      });
      await reread(being);

      const label = `${being.name}: ${number.label} ${before} → ${after}`;

      history.push({
        label,
        undo: async () => {
          if (number.own) {
            await setStat(tenantId, being.entity_id, definition, before, {
              value: after,
              own: true,
            });
          } else {
            await clearStat(tenantId, being.entity_id, definition, { value: after, own: true });
          }

          await reread(being);
        },
      });
      toast?.dismiss();
      toast =
        currentShell()?.undoable({ title: label, text: 'by you', undo: () => void undo() }) ?? null;
      say(status, '');
    } catch (error) {
      say(status, errorMessage(error), true);
      if (error instanceof StatChangedError) await reread(being).catch(() => {});
    } finally {
      busy = false;
      await draw();
    }
  }

  async function undo() {
    const last = history.pop();

    if (!last || busy) return;

    busy = true;

    try {
      await last.undo();
      toast?.dismiss();
      toast = null;
      say(status, '');
    } catch (error) {
      say(status, errorMessage(error), true);
    } finally {
      busy = false;
      await draw();
    }
  }

  undoButton.addEventListener('click', () => void undo());

  // ---- drawing ----------------------------------------------------------------------------------

  let latest = 0;

  function remember() {
    const url = new URL(window.location.href);
    const set = (key: string, value: string) =>
      value ? url.searchParams.set(key, value) : url.searchParams.delete(key);

    set('q', search.value.trim());
    set('kind', checked(kindSwitch) === 'all' ? '' : checked(kindSwitch));
    set('mine', checked(scopeSwitch) === 'mine' ? '1' : '');
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
      kind: checked(kindSwitch) as Kind,
      mine: checked(scopeSwitch) === 'mine' ? ownedIds : null,
      campaign,
    };
  }

  function drawing(): Drawing {
    return {
      tenantAddress,
      numbers,
      playedBy,
      rostersKnown,
      owned: ownedIds,
      columns: columnsOf(vocabulary),
      canRun,
      playing,
      step: (being, name, direction) => void step(being, name, direction),
      observe: (row, being) => pictures.observe(row, being.entity_id, being.name),
    };
  }

  async function draw() {
    const turn = ++latest;
    remember();

    const mine = checked(scopeSwitch) === 'mine';

    title.textContent = mine ? 'My beings' : 'All beings';
    modeSwitch.hidden = view !== 'side';
    undoButton.hidden = view !== 'side' || !playing;
    undoButton.disabled = history.size === 0;

    try {
      const filters = await currentFilters();
      const shown = filterBeings(beings, filters);

      if (turn !== latest) return;

      pictures.reset();

      if (shown.length === 0) {
        list.hidden = true;
        side.hidden = true;
        showEmpty(mine);
        return;
      }

      empty.hidden = true;
      // Rows and cards show at once, and take their numbers as they arrive; side by side is all numbers.
      const draw = view === 'rows' ? drawRows : view === 'cards' ? drawCards : drawSide;
      const target = view === 'side' ? side : list;
      const other = view === 'side' ? list : side;

      other.hidden = true;
      target.replaceChildren(draw(shown, drawing()));
      target.hidden = false;
      say(status, `${shown.length} ${shown.length === 1 ? 'being' : 'beings'}`);

      if (shown.some((being) => !numbers.has(being.entity_id))) {
        if (view === 'side') say(status, 'Loading numbers…');
        await loadNumbers(shown);
        if (turn !== latest) return;

        pictures.reset();
        target.replaceChildren(draw(shown, drawing()));
        say(status, `${shown.length} ${shown.length === 1 ? 'being' : 'beings'}`);
      }
    } catch (error) {
      if (turn === latest) say(status, errorMessage(error), true);
    }
  }

  const clear = required<HTMLButtonElement>(root, '[data-clear]');
  const emptyNew = required<HTMLButtonElement>(root, '[data-empty-new]');

  function showEmpty(mine: boolean) {
    const filtered =
      search.value.trim() !== '' ||
      checked(kindSwitch) !== 'all' ||
      mine ||
      campaignSelect.value !== '';
    const maker = gm || member;

    empty.hidden = false;
    say(status, '');
    required<HTMLElement>(empty, '[data-empty-title]').textContent = filtered
      ? 'Nothing matches.'
      : 'No being yet.';
    required<HTMLElement>(empty, '[data-empty-text]').textContent = filtered
      ? 'No being matches that, among the ones you can read.'
      : maker
        ? 'Make the first one. It has no player until you hand it over.'
        : 'Someone who runs the table makes a being, then hands it to a player.';
    clear.hidden = !filtered;
    emptyNew.hidden = filtered || !maker;
  }

  clear.addEventListener('click', () => {
    search.value = '';
    for (const radio of radios(kindSwitch)) radio.checked = radio.value === 'all';
    for (const radio of radios(scopeSwitch)) radio.checked = radio.value === 'all';
    campaignSelect.value = '';
    void draw();
  });

  let debounce: ReturnType<typeof setTimeout> | undefined;

  search.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => void draw(), 150);
  });

  campaignSelect.addEventListener('change', () => void draw());

  for (const group of [kindSwitch, scopeSwitch]) {
    group.addEventListener('change', () => void draw());
  }

  viewSwitch.addEventListener('change', () => {
    const value = checked(viewSwitch);

    if (!isListView(value)) return;

    view = value;
    rememberView(view);
    void draw();
  });

  modeSwitch.addEventListener('change', () => {
    playing = checked(modeSwitch) === 'play';
    void draw();
  });

  // ---- making one --------------------------------------------------------------------------------

  const wire = (dialog: HTMLDialogElement) => {
    fadeOnDismiss(dialog);
    dialog.querySelector('[data-cancel]')?.addEventListener('click', () => closeDialog(dialog));
  };

  // Making one is for those who run a campaign or the library; the API still decides.
  if (gm || member) {
    const dialog = required<HTMLDialogElement>(root, '[data-create-dialog]');
    const form = required<HTMLFormElement>(dialog, '[data-create-form]');
    const name = required<HTMLInputElement>(form, '[data-create-name]');
    const create = required<HTMLButtonElement>(form, '[data-create]');
    const createStatus = required<HTMLElement>(form, '[data-create-status]');
    const open = () => {
      openDialog(dialog);
      name.focus();
    };

    wire(dialog);
    newButton.hidden = false;
    newButton.addEventListener('click', open);
    emptyNew.addEventListener('click', open);

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
    const dialog = required<HTMLDialogElement>(root, '[data-own-dialog]');
    const ownForm = required<HTMLFormElement>(dialog, '[data-own-form]');
    const seat = required<HTMLSelectElement>(ownForm, '[data-own-seat]');
    const ownName = required<HTMLInputElement>(ownForm, '[data-own-name]');
    const ownCreate = required<HTMLButtonElement>(ownForm, '[data-own-create]');
    const ownStatus = required<HTMLElement>(ownForm, '[data-own-status]');
    const names = new Map(campaigns.map((campaign) => [campaign.id, campaign.name]));

    for (const option of seatOptions(seats, names)) {
      seat.append(new Option(option.label, option.seatId));
    }

    wire(dialog);
    newOwnButton.hidden = false;
    newOwnButton.addEventListener('click', () => {
      openDialog(dialog);
      ownName.focus();
    });

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
