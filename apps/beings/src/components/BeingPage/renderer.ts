// A being's own page (ADR 0271, 0272): everything about it in one place, and for those who may, the
// sections that change it. The parts don't know of each other; this holds what they share (what is
// shown, who is looking) and tells each when something changed. Every control is a convenience: the
// API refuses what the viewer may not do, and the page says so.

import { openMenu } from '@lorenzo/app-shell';
import { descriptionOf, getCharacter, pictureOf } from '../../lib/being';
import { kindLabel } from '../../lib/beingList';
import { BRANDING_CSS_URL } from '../../lib/config';
import type { Renderer } from '../../lib/descriptions';
import { getEntityDetail } from '../../lib/entities';
import { renderDescriptionEdit, renderSlugEditor, renderTagEditor } from '../../lib/entityParts';
import { errorMessage } from '../../lib/errorMessage';
import { DEFAULT_GM_WORDS, gmWordsOfBeing } from '../../lib/gmTitle';
import { gmCampaignsIn, isTenantMember, listCampaigns, myBeingIds, viewerId } from '../../lib/me';
import type { Person } from '../../lib/people';
import { currentShell } from '../../lib/shell';
import { backTo, stepText, whoLabel } from '../../lib/statHistory';
import { listStatSteps } from '../../lib/statSteps';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { getTenant } from '../../lib/tenants';
import type { Character, EntityDetail } from '../../lib/types';
import { renderBeingEvents } from '../BeingEvents/renderer';
import { renderBeingNotes } from '../BeingNotes/renderer';
import { renderBeingRelationships } from '../BeingRelationships/renderer';
import { renderBeingView } from '../BeingView/renderer';
import { renderDatasheet } from '../Datasheet/renderer';
import { renderDeleteBeing } from '../DeleteBeing/renderer';
import { renderHandOver } from '../HandOver/renderer';
import { renderInventorySummary } from '../InventorySummary/renderer';
import { renderNameEdit } from '../NameEdit/renderer';
import { renderPeople } from '../People/renderer';
import { renderPictureEdit } from '../PictureEdit/renderer';
import { renderSheetControls } from '../SheetControls/renderer';
import { renderStatBand } from '../StatBand/renderer';

export type BeingPageOptions = {
  // The <BeingPage />.
  root: HTMLElement;
  tenantId: string;
  // What the address calls the library: an id or a slug.
  tenantAddress: string;
  renderer: Renderer;
};

export type RenderedBeingPage = {
  // Shows the being, and reveals the page.
  show(entityId: string): Promise<void>;
};

const required = requiredIn('Being page');

export function renderBeingPage(options: BeingPageOptions): RenderedBeingPage {
  const { root, tenantId, tenantAddress, renderer } = options;

  const back = required<HTMLAnchorElement>(root, '[data-back]');
  const title = required<HTMLElement>(root, '[data-title]');
  const kind = required<HTMLElement>(root, '[data-kind]');
  const slug = required<HTMLElement>(root, '[data-link-name]');
  const played = required<HTMLElement>(root, '[data-played]');
  const campaignsLine = required<HTMLElement>(root, '[data-campaigns]');
  const campaignText = required<HTMLElement>(root, '[data-campaign-text]');
  const more = required<HTMLButtonElement>(root, '[data-more]');
  const nameSection = required<HTMLElement>(root, '[data-name-section] > div');
  const saveStatus = required<HTMLElement>(root, '[data-save-status]');
  const appears = required<HTMLAnchorElement>(root, '[data-appears]');
  const bandUndo = required<HTMLButtonElement>(root, '[data-band-undo]');
  const bandHistory = required<HTMLButtonElement>(root, '[data-band-history]');
  const statBand = renderStatBand({
    root: required<HTMLElement>(root, '[data-stat-band]'),
    page: root,
    lines: required<HTMLElement>(root, '[data-ds-lines]'),
    tenantId,
    onChanged: (entity) => showEntity(entity),
    announce: (message) => controls.announce(message),
    onSteps: (count, last) => {
      bandUndo.disabled = count === 0;
      controls.setSteps(count, last);
    },
    say: (message, failed) => say(saveStatus, message, failed),
  });

  bandUndo.addEventListener('click', () => void statBand.undo());
  // History (BN9): the steps the API keeps, who made each, and going back to before any of them.
  bandHistory.addEventListener('click', async () => {
    const entity = shown;

    if (!entity) return;

    try {
      const [steps, me] = await Promise.all([
        listStatSteps(tenantId, entity.id),
        viewerId().catch(() => ''),
      ]);

      if (steps.length === 0) {
        currentShell()?.toast({ title: 'No steps yet', text: 'Changes made in Play show here.' });
        return;
      }

      openMenu(
        bandHistory,
        [
          { heading: `Steps, newest first (${steps.length} of 30)` },
          ...steps.map((step, index) => ({
            label: `Undo back to before: ${stepText(step)}, by ${whoLabel(step, me)}, ${new Date(
              step.created_at,
            ).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
            icon: 'undo',
            run: () => void statBand.restore(backTo(steps, index)),
          })),
        ],
        { label: 'History', sprite: `${BRANDING_CSS_URL}/icons.svg` },
      );
    } catch (error) {
      say(saveStatus, errorMessage(error), true);
    }
  });

  back.href = `/beings/?tenant=${encodeURIComponent(tenantAddress)}`;

  let shown: EntityDetail | null = null;
  let character: Character | null = null;
  let canEdit = false;

  const current = (): EntityDetail => {
    if (!shown) throw new Error('Nothing is shown yet.');

    return shown;
  };

  const deletion = renderDeleteBeing({
    root: required<HTMLElement>(root, '[data-delete-being]'),
    tenantId,
    current,
    onDeleted: () => window.location.assign(back.href),
  });

  // Reads the being again after a change and shows it.
  async function refresh() {
    showEntity(await getEntityDetail(tenantId, current().id));
  }

  function showSlug(value: string | null) {
    slug.hidden = !value;
    slug.textContent = value ?? '';

    // The address names the being by its link name, once it has one (ADR 0135).
    const url = new URL(window.location.href);

    if (value) {
      url.searchParams.set('slug', value);
      url.searchParams.delete('id');
    } else if (shown) {
      url.searchParams.set('id', shown.id);
      url.searchParams.delete('slug');
    }

    window.history.replaceState(window.history.state, '', url);
  }

  const view = renderBeingView(root, { renderer, tenantId });
  const people = renderPeople(required<HTMLElement>(root, '[data-people]'));
  const events = renderBeingEvents(required<HTMLElement>(root, '[data-being-events]'));
  const relationships = renderBeingRelationships(
    required<HTMLElement>(root, '[data-being-relationships]'),
  );
  const inventory = renderInventorySummary(required<HTMLElement>(root, '[data-inventory]'));
  const description = renderDescriptionEdit({
    root: required<HTMLElement>(root, '[data-description-edit]'),
    tenantId,
    renderer,
    onSaved: () => void refresh(),
  });
  const datasheet = renderDatasheet({
    root: required<HTMLElement>(root, '[data-datasheet]'),
    tenantId,
    renderer,
    vocabulary: () => statBand.vocabulary(),
  });
  const controls = renderSheetControls({
    root,
    onLayout: (layout) => {
      if (shown) {
        redrawStats(shown);
        if (layout === 'datasheet') void datasheet.load(shown.id);
      }
    },
    onMode: (mode) => {
      // The description's way into its form is for Read, not for the table.
      description.allow(canEdit && mode === 'read');
      if (shown) redrawStats(shown);
    },
  });
  const nameEdit = renderNameEdit({
    root: required<HTMLFormElement>(root, '[data-name-edit]'),
    tenantId,
    onSaved: () => void refresh(),
  });
  const pictureEdit = renderPictureEdit({
    root: required<HTMLElement>(root, '[data-picture-edit]'),
    tenantId,
    onChanged: () => void refresh(),
  });
  const slugEditor = renderSlugEditor({
    root: required<HTMLElement>(root, '[data-slug-editor]'),
    tenantId,
    onSaved: showSlug,
  });
  const tagEditor = renderTagEditor({
    root: required<HTMLElement>(root, '[data-tag-editor]'),
    tenantId,
    onChanged: () => void refresh(),
  });
  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      currentShell()?.toast({ kind: 'ok', title: 'Link copied' });
    } catch {
      currentShell()?.toast({ kind: 'error', title: "Couldn't copy the link" });
    }
  }

  // The page's menu (BN6): the things done to the being as a whole.
  more.addEventListener('click', () => {
    openMenu(
      more,
      [
        { label: 'Edit details', icon: 'edit', run: () => controls.toggleDetails() },
        { label: 'Copy link', icon: 'link', run: () => void copyLink() },
        { separator: true },
        { label: 'Delete being…', icon: 'delete', danger: true, run: () => void deletion.run() },
      ],
      { label: 'More for this being', sprite: `${BRANDING_CSS_URL}/icons.svg` },
    );
  });

  /** Who plays it and in which campaign, in the line under the name and in the rail. */
  function showPeople(people: readonly Person[]) {
    const names = people.map((person) => person.name);
    const campaigns = [
      ...new Set(people.flatMap((person) => (person.campaign ? [person.campaign] : []))),
    ];

    played.textContent = names.length > 0 ? `· played by ${names.join(', ')}` : '· not played';
    campaignsLine.textContent = campaigns.length > 0 ? `· ${campaigns.join(', ')}` : '';
    campaignText.textContent = campaigns.length > 0 ? campaigns.join(', ') : 'None';
  }

  function showEntity(entity: EntityDetail) {
    shown = entity;
    document.title = `${entity.name} — Lorenzo Beings`;
    title.textContent = entity.name;
    controls.setName(entity.name);
    showSlug(entity.slug);
    appears.href = `/appears/?tenant=${encodeURIComponent(tenantAddress)}&id=${entity.id}`;
    view.show(entity);
    description.show({
      entityId: entity.id,
      name: entity.name,
      hasDescription: descriptionOf(entity) !== '',
    });
    pictureEdit.load(entity.id, pictureOf(entity) !== undefined);

    datasheet.show({ id: entity.id, name: entity.name, information: entity.information });
    redrawStats(entity);
  }

  // The numbers and tags as the mode shows them, and the few the sticky bar keeps in view.
  function redrawStats(entity: EntityDetail) {
    const drawn = statBand.show(entity, controls.mode(), canEdit, controls.layout());

    datasheet.setHasStats(drawn.length > 0);
  }

  return {
    async show(entityId) {
      root.hidden = false;

      const [entity, tenant] = await Promise.all([
        getEntityDetail(tenantId, entityId),
        getTenant(tenantId).catch(() => null),
      ]);

      character = await getCharacter(tenantId, entityId).catch(() => null);
      kind.textContent = character ? kindLabel(character) : 'NPC';
      await statBand.load(tenant?.being_stat_group_id ?? null);
      showEntity(entity);

      // Asked for the datasheet before the being had arrived (a link, or a quick hand).
      if (controls.layout() === 'datasheet') void datasheet.load(entityId);

      void people.load(tenantId, character).then(showPeople);
      void inventory.load(tenantId, tenantAddress, entityId);
      void events.load(tenantId, tenantAddress, entityId);
      void relationships.load(tenantId, entityId, entity.name);

      // Who gets the writing controls: those who run a campaign or the library, and whoever plays
      // this being. A convenience only; the API decides every write.
      const [gmCampaigns, member, mine, inRepository, campaigns] = await Promise.all([
        gmCampaignsIn(tenantId).catch(() => []),
        isTenantMember(tenantId).catch(() => false),
        myBeingIds(tenantId).catch(() => new Set<string>()),
        // A repository's beings are opened here too, and their Everyone's notes go with every copy.
        Promise.resolve(tenant?.kind === 'repository'),
        // What the campaigns it is in call their game master (ADR 0294); not knowing says "GM".
        listCampaigns(tenantId).catch(() => []),
      ]);
      const runsTheTable = gmCampaigns.length > 0 || member;

      canEdit = runsTheTable || mine.has(entityId);
      deletion.allow(canEdit);

      const notes = renderBeingNotes(required<HTMLElement>(root, '[data-being-notes]'), {
        tenantId,
        renderer,
        beingId: entityId,
        // A repository's entries belong to no campaign: they say "GM".
        words: inRepository ? DEFAULT_GM_WORDS : gmWordsOfBeing(character, campaigns),
        inRepository,
      });

      void notes.load({ canWrite: canEdit, runsTheTable });
      const words = inRepository ? DEFAULT_GM_WORDS : gmWordsOfBeing(character, campaigns);

      controls.setGmWord(words.title);
      controls.allowEdit(canEdit, tenantId, entityId);
      // Who may write is known now: the numbers and tags can show their controls.
      redrawStats(current());

      if (!canEdit) return;

      void slugEditor.load(entityId, entity.name, 'item');
      void tagEditor.load(entityId);

      // Renaming and handing over are of a character: a bare being has no such row (ADR 0031).
      if (character) {
        nameSection.hidden = false;
        nameEdit.load(entityId, entity.name);
      }

      if (character && gmCampaigns.length > 0) {
        const handOver = renderHandOver({
          root: required<HTMLElement>(root, '[data-hand-over]'),
          tenantId,
          campaigns: gmCampaigns,
          onDone: () => {
            void getCharacter(tenantId, entityId).then((updated) => {
              character = updated;
              kind.textContent = updated ? kindLabel(updated) : 'NPC';
              void people.load(tenantId, updated).then(showPeople);
            });
          },
        });

        handOver.load(entityId);
      }
    },
  };
}
