// A being's own page (ADR 0271, 0272): everything about it in one place, and for those who may, the
// sections that change it. The parts don't know of each other; this holds what they share (what is
// shown, who is looking) and tells each when something changed. Every control is a convenience: the
// API refuses what the viewer may not do, and the page says so.

import { descriptionOf, getCharacter, pictureOf } from '../../lib/being';
import { kindLabel } from '../../lib/beingList';
import type { Renderer } from '../../lib/descriptions';
import { getEntityDetail } from '../../lib/entities';
import { DEFAULT_GM_WORDS, gmWordsOfBeing } from '../../lib/gmTitle';
import { gmCampaignsIn, isTenantMember, listCampaigns, myBeingIds } from '../../lib/me';
import { valueText, vitalsOf } from '../../lib/statBand';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { getTenant } from '../../lib/tenants';
import type { Character, EntityDetail } from '../../lib/types';
import { renderBeingNotes } from '../BeingNotes/renderer';
import { renderBeingView } from '../BeingView/renderer';
import { renderDatasheet } from '../Datasheet/renderer';
import { renderDescriptionEdit } from '../DescriptionEdit/renderer';
import { renderHandOver } from '../HandOver/renderer';
import { renderInventorySummary } from '../InventorySummary/renderer';
import { renderNameEdit } from '../NameEdit/renderer';
import { renderPeople } from '../People/renderer';
import { renderPictureEdit } from '../PictureEdit/renderer';
import { renderSheetControls } from '../SheetControls/renderer';
import { renderSlugEditor } from '../SlugEditor/renderer';
import { renderStatBand } from '../StatBand/renderer';
import { renderTagEditor } from '../TagEditor/renderer';

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
  const copyLink = required<HTMLButtonElement>(root, '[data-copy-link]');
  const nameSection = required<HTMLElement>(root, '[data-name-section] > div');
  const saveStatus = required<HTMLElement>(root, '[data-save-status]');
  const statBand = renderStatBand({
    root: required<HTMLElement>(root, '[data-stat-band]'),
    page: root,
    lines: required<HTMLElement>(root, '[data-ds-lines]'),
    tenantId,
    onChanged: (entity) => showEntity(entity),
    announce: (message) => controls.announce(message),
    say: (message, failed) => say(saveStatus, message, failed),
  });

  back.href = `/beings/?tenant=${encodeURIComponent(tenantAddress)}`;

  let shown: EntityDetail | null = null;
  let character: Character | null = null;
  let canEdit = false;

  const current = (): EntityDetail => {
    if (!shown) throw new Error('Nothing is shown yet.');

    return shown;
  };

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

  const view = renderBeingView(root, { renderer });
  const people = renderPeople(required<HTMLElement>(root, '[data-people]'));
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
      // The description's way into its form is for building the being, not for reading it.
      description.allow(canEdit && mode === 'edit');
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
  copyLink.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      copyLink.textContent = 'Copied!';
    } catch {
      copyLink.textContent = "Couldn't copy";
    } finally {
      window.setTimeout(() => {
        copyLink.textContent = 'Copy link';
      }, 1500);
    }
  });

  function showEntity(entity: EntityDetail) {
    shown = entity;
    document.title = `${entity.name} — Lorenzo Beings`;
    title.textContent = entity.name;
    controls.setName(entity.name);
    showSlug(entity.slug);
    view.show(entity);
    description.show({
      entityId: entity.id,
      name: entity.name,
      hasDescription: descriptionOf(entity) !== '',
    });
    pictureEdit.load(entity.id, pictureOf(entity) !== undefined);

    datasheet.show({ id: entity.id, name: entity.name, description: descriptionOf(entity) });
    redrawStats(entity);
  }

  // The numbers and tags as the mode shows them, and the few the sticky bar keeps in view.
  function redrawStats(entity: EntityDetail) {
    const drawn = statBand.show(entity, controls.mode(), canEdit, controls.layout());

    datasheet.setHasStats(drawn.length > 0);

    controls.setVitals(
      vitalsOf(drawn).map((tile) => ({ label: tile.label, value: valueText(tile) })),
    );
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

      void people.load(tenantId, character);
      void inventory.load(tenantId, tenantAddress, entityId);

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

      const notes = renderBeingNotes(required<HTMLElement>(root, '[data-being-notes]'), {
        tenantId,
        renderer,
        beingId: entityId,
        // A repository's entries belong to no campaign: they say "GM".
        words: inRepository ? DEFAULT_GM_WORDS : gmWordsOfBeing(character, campaigns),
        inRepository,
      });

      void notes.load({ canWrite: canEdit, runsTheTable });
      controls.allowEdit(
        canEdit,
        'Only the people who run this table, or play this being, can edit it.',
      );
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
              void people.load(tenantId, updated);
            });
          },
        });

        handOver.load(entityId);
      }
    },
  };
}
