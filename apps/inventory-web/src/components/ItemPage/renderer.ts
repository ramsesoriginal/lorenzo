// An item's or an instance's own page: everything about it in one place, and for GMs the
// sections that change it. The parts don't know of each other; this holds what they share (what
// is shown, and who is looking) and tells each when something changed.

import { listMyCharacters } from '../../lib/characters';
import type { Renderer } from '../../lib/descriptions';
import type { FoundItem } from '../../lib/itemLookup';
import { getCatalogItem, getEntityDetail, getItemInstance } from '../../lib/items';
import { isCampaignGm } from '../../lib/me';
import { requiredIn } from '../../lib/template';
import type { ItemBase, ItemInstance } from '../../lib/types';
import { renderAncestryTree } from '../AncestryTree/renderer';
import { renderDescriptionEdit } from '../DescriptionEdit/renderer';
import { renderInformation } from '../Information/renderer';
import { renderItemView } from '../ItemView/renderer';
import { renderMentionedIn } from '../MentionedIn/renderer';
import { type Reader, renderNotes } from '../Notes/renderer';
import { renderSlugEditor } from '../SlugEditor/renderer';
import { renderTagEditor } from '../TagEditor/renderer';
import { renderUsedBy } from '../UsedBy/renderer';

export type ItemPageOptions = {
  // The <ItemPage />.
  root: HTMLElement;
  tenantId: string;
  renderer: Renderer;
};

export type RenderedItemPage = {
  // Shows what was found, and reveals the page.
  show(found: FoundItem): Promise<void>;
};

const required = requiredIn('Item page');

export function renderItemPage(options: ItemPageOptions): RenderedItemPage {
  const { root, tenantId, renderer } = options;

  const title = required<HTMLElement>(root, '[data-title]');
  const slug = required<HTMLElement>(root, '[data-slug]');
  const quantity = required<HTMLElement>(root, '[data-quantity]');
  const notesSection = required<HTMLElement>(root, '[data-notes-section]');
  const gmSections = required<HTMLElement>(root, '[data-gm]');
  const copyLink = required<HTMLButtonElement>(root, '[data-copy-link]');

  // What is shown, and whether it's an instance, which says which endpoint reads it again.
  let shown: ItemBase | null = null;
  let isInstance = false;
  // Who writes here, and the character that reads a private note (ADR 0113).
  let viewerIsGm = false;
  let reader: Reader | null = null;

  function current(): ItemBase {
    if (!shown) throw new Error('Nothing is shown yet.');

    return shown;
  }

  function showSlug(value: string | null) {
    slug.hidden = !value;
    slug.textContent = value ?? '';
  }

  function showNotes() {
    if (!isInstance) return;

    notesSection.hidden = false;
    void notes.load(current().entity_id, { canWrite: viewerIsGm || reader !== null, reader });
  }

  function showInformation() {
    void information.load(current().entity_id);
  }

  function showGmSections() {
    const item = current();

    gmSections.hidden = false;
    void slugEditor.load(item.entity_id, item.title, isInstance ? 'instance' : 'item');
    void tagEditor.load(item.entity_id);
    showInformation();
  }

  // Reads the item again after a change and shows it.
  async function refresh() {
    const { entity_id: entityId } = current();

    showItem(
      isInstance
        ? await getItemInstance(tenantId, entityId)
        : await getCatalogItem(tenantId, entityId),
    );
  }

  const itemView = renderItemView(required<HTMLElement>(root, '[data-view]'), {
    tenantId,
    renderer,
  });
  const ancestryTree = renderAncestryTree({
    root: required<HTMLElement>(root, '[data-ancestry]'),
    tenantId,
  });
  const usedBy = renderUsedBy({ root: required<HTMLElement>(root, '[data-used-by]'), tenantId });
  const mentionedIn = renderMentionedIn({
    root: required<HTMLElement>(root, '[data-mentioned-in]'),
    tenantId,
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
  // An instance's notes, for everyone (ADR 0113). The GM's Information section lists them too,
  // so a change in either shows in the other.
  const notes = renderNotes(required<HTMLElement>(notesSection, '[data-notes-list]'), {
    tenantId,
    renderer,
    rowHeading: 'h3',
    onChanged: () => viewerIsGm && showInformation(),
  });
  const information = renderInformation(required<HTMLElement>(root, '[data-information]'), {
    tenantId,
    renderer,
    onChanged: () => {
      void refresh();
      showNotes();
    },
  });
  const description = renderDescriptionEdit({
    root: required<HTMLElement>(root, '[data-description-edit]'),
    tenantId,
    renderer,
    onSaved: () => void refresh().then(showGmSections),
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

  function showItem(item: ItemBase | ItemInstance) {
    shown = item;
    document.title = `${item.title} — Lorenzo`;
    title.textContent = item.title;

    // An instance carries its slug; a catalog item's is read from its entity (ADR 0113).
    if ('slug' in item) showSlug(item.slug);

    const stacked = Boolean(item.quantity && item.quantity > 1);

    quantity.hidden = !stacked;
    quantity.textContent = stacked ? `×${item.quantity}` : '';
    itemView.show(item);
    description.show(item);
  }

  return {
    async show(found) {
      isInstance = found.instance;
      root.hidden = false;
      showItem(found.item);

      const entityId = found.item.entity_id;

      if (isInstance) {
        void ancestryTree.load(found.item.prototype_ids[0] ?? null);
      } else {
        void ancestryTree.load(entityId);
        void usedBy.load(entityId);
        void getEntityDetail(tenantId, entityId).then(
          (entity) => showSlug(entity.slug),
          () => {},
        );
      }

      void mentionedIn.load(entityId);

      // GMs write here (ADR 0108, 0112, 0113); a player writes notes on what their character
      // owns. The API still decides.
      const owner = 'owner_entity_id' in found.item ? found.item.owner_entity_id : null;
      const [gm, mine] = await Promise.all([
        isCampaignGm(tenantId).catch(() => false),
        owner
          ? listMyCharacters(tenantId).then(
              (own) => own.items,
              () => [],
            )
          : [],
      ]);

      viewerIsGm = gm;
      reader = mine.find((character) => character.entity_id === owner) ?? null;
      showNotes();
      description.allow(gm);

      if (gm) showGmSections();
    },
  };
}
