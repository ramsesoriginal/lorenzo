// Looking inside a repository (RFC 0038 §5, ADR 0293): what the Owner features, drawn as cards with
// the text, pictures and stat values the API says this reader may see, and, for a visitor of a
// repository whose Owner opened every entry, a searchable, paged list of them, each opening in a
// dialog. The same drawing serves a repository's page in Discover and in Shelf; they differ in the
// `PreviewSource` they give it (lib/previewApi.ts). Only the newest `show` paints, and an answer that
// arrives after another began is dropped.

import { showLorenzoScript } from '../../lib/lorenzoScript';
import {
  ALL_ENTRIES_HEADING,
  ENTRY_PAGE_SIZE,
  FEATURED_LABEL,
  FIND_AN_ENTRY,
  kindsLine,
  listCount,
  NO_ENTRY_MATCHES,
  offersAllEntries,
  PREVIEW_HEADING,
  type PreviewLevel,
  parentsText,
  preferredLocales,
  previewLine,
  type Reader,
  statGroups,
  textLines,
  textNote,
} from '../../lib/preview';
import type { PreviewSource } from '../../lib/previewApi';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import type { PreviewEntityOut, RepositoryEntityOut } from '../../lib/types';

const required = requiredIn('Preview');

export type PreviewOptions = {
  // Whether this page draws the list of every entry itself (Discover does; Shelf has its own list
  // of names and opens an entry from it).
  list: boolean;
};

export type PreviewView = {
  // Reads the preview of a repository and draws it. `isCurrent` says whether the page still shows
  // that repository.
  // Resolves to the Owner's switch, or null where nothing was read (a failure, or the page moved on).
  show(
    source: PreviewSource,
    reader: Reader,
    isCurrent: () => boolean,
  ): Promise<PreviewLevel | null>;
  // Opens one entry in the dialog.
  open(entityId: string): Promise<void>;
  hide(): void;
};

function pair(list: HTMLElement, term: string, value: string): void {
  const dt = document.createElement('dt');
  const dd = document.createElement('dd');

  dt.textContent = term;
  dd.textContent = value;
  list.append(dt, dd);
}

// `root` is whatever holds a <Preview />.
export function createPreview(root: HTMLElement, options: PreviewOptions): PreviewView {
  const section = required<HTMLElement>(root, '[data-preview]');
  const error = required<HTMLElement>(section, '[data-preview-error]');
  const line = required<HTMLElement>(section, '[data-preview-line]');
  const featured = required<HTMLElement>(section, '[data-preview-featured]');
  const all = required<HTMLElement>(section, '[data-preview-all]');
  const search = required<HTMLInputElement>(section, '[data-preview-search]');
  const count = required<HTMLElement>(section, '[data-preview-count]');
  const list = required<HTMLElement>(section, '[data-preview-list]');
  const empty = required<HTMLElement>(section, '[data-preview-empty]');
  const more = required<HTMLButtonElement>(section, '[data-preview-more]');
  const allError = required<HTMLElement>(section, '[data-preview-all-error]');
  const dialog = required<HTMLDialogElement>(section, '[data-preview-dialog]');
  const dialogError = required<HTMLElement>(dialog, '[data-preview-dialog-error]');
  const dialogLoading = required<HTMLElement>(dialog, '[data-preview-dialog-loading]');
  const dialogBody = required<HTMLElement>(dialog, '[data-preview-dialog-body]');

  required<HTMLElement>(section, '[data-preview-heading]').textContent = PREVIEW_HEADING;
  required<HTMLElement>(section, '[data-preview-all-heading]').textContent = ALL_ENTRIES_HEADING;
  required<HTMLElement>(section, '[data-preview-search-label]').textContent = FIND_AN_ENTRY;
  empty.textContent = NO_ENTRY_MATCHES;

  // A page that has a list of entries of its own (Shelf's) has no use for this one, and a second
  // search box that is never shown would still be found by its label.
  if (!options.list) all.remove();

  const locales = preferredLocales(
    typeof navigator === 'undefined' ? undefined : navigator.languages,
  );

  let source: PreviewSource | null = null;
  // Only the newest show paints, and only the newest list read.
  let latest = 0;
  const entries = { loaded: [] as RepositoryEntityOut[], page: 0, total: 0, query: '' };
  let opening = 0;

  function paintPictures(
    box: HTMLElement,
    entityId: string,
    title: string,
    pictures: PreviewEntityOut['information'][number]['pictures'],
    isCurrent: () => boolean,
  ): void {
    box.replaceChildren();
    box.hidden = pictures.length === 0;

    for (const picture of pictures) {
      const img = document.createElement('img');

      img.alt = title;
      img.loading = 'lazy';
      img.className = 'preview-picture';
      img.hidden = true;
      box.append(img);

      void source
        ?.picture(entityId, picture.id)
        .then((url) => {
          if (!isCurrent()) return;

          img.src = url;
          img.hidden = false;
        })
        .catch(() => {
          // A picture that does not come is left out; the text stands.
        });
    }
  }

  // One entry as a card.
  function card(entry: PreviewEntityOut, isCurrent: () => boolean): HTMLElement {
    const article = cloneRoot(section, '[data-preview-entry-template]');
    const featuredPill = required<HTMLElement>(article, '[data-featured]');
    const parents = parentsText(entry);
    const note = textNote(entry);
    const texts = required<HTMLElement>(article, '[data-texts]');
    const stats = required<HTMLElement>(article, '[data-stats]');

    required<HTMLElement>(article, '[data-name]').textContent = entry.name;
    featuredPill.textContent = entry.featured ? FEATURED_LABEL : '';
    featuredPill.hidden = !entry.featured;
    required<HTMLElement>(article, '[data-kinds]').textContent = kindsLine(entry);

    const parentsLine = required<HTMLElement>(article, '[data-parents]');

    parentsLine.textContent = parents ?? '';
    parentsLine.hidden = parents === null;

    const noteLine = required<HTMLElement>(article, '[data-note]');

    noteLine.textContent = note ?? '';
    noteLine.hidden = note === null;

    texts.replaceChildren(
      ...textLines(entry, locales).map((row) => {
        const item = cloneRoot(section, '[data-preview-text-template]');
        const content = required<HTMLElement>(item, '[data-content]');

        required<HTMLElement>(item, '[data-title]').textContent = row.title;
        showLorenzoScript(content, row.text);
        paintPictures(
          required<HTMLElement>(item, '[data-pictures]'),
          entry.id,
          row.title,
          row.pictures,
          isCurrent,
        );

        return item;
      }),
    );

    const groups = statGroups(entry.stats);

    stats.replaceChildren(
      ...groups.map((group) => {
        const item = cloneRoot(section, '[data-preview-stat-group-template]');
        const values = required<HTMLElement>(item, '[data-values]');

        required<HTMLElement>(item, '[data-group]').textContent = group.group;

        for (const stat of group.stats) pair(values, stat.name, stat.value);

        return item;
      }),
    );
    stats.hidden = groups.length === 0;

    return article;
  }

  async function open(entityId: string): Promise<void> {
    const reading = source;
    const turn = ++opening;

    if (!reading) return;

    dialogError.hidden = true;
    dialogBody.replaceChildren();
    dialogLoading.hidden = false;

    if (!dialog.open) dialog.showModal();

    try {
      const entry = await reading.entry(entityId);

      if (turn !== opening) return;

      dialogLoading.hidden = true;

      if (!entry) {
        dialogError.textContent = 'This entry is not open to look at.';
        dialogError.hidden = false;

        return;
      }

      dialog.setAttribute('aria-label', entry.name);
      dialogBody.replaceChildren(card(entry, () => turn === opening && dialog.open));
    } catch (cause) {
      if (turn !== opening) return;

      dialogLoading.hidden = true;
      sayError(dialogError, cause);
    }
  }

  required<HTMLElement>(dialog, '[data-preview-close]').addEventListener('click', () => {
    dialog.close();
  });
  dialog.addEventListener('close', () => {
    opening++;
    dialogBody.replaceChildren();
  });

  function paintList(): void {
    list.replaceChildren(
      ...entries.loaded.map((entry) => {
        const item = cloneRoot(section, '[data-preview-item-template]');
        const look = required<HTMLButtonElement>(item, '[data-look]');

        required<HTMLElement>(item, '[data-name]').textContent = entry.name;
        required<HTMLElement>(item, '[data-kinds]').textContent = entry.kinds
          .map((kind) => kindsLine({ kinds: [kind] }))
          .join(', ');
        look.setAttribute('aria-label', `Look at ${entry.name}`);
        look.addEventListener('click', () => void open(entry.id));

        return item;
      }),
    );
    count.textContent = entries.total === 0 ? '' : listCount(entries.loaded.length, entries.total);
    empty.hidden = entries.loaded.length > 0;
    more.hidden = entries.loaded.length >= entries.total;
  }

  async function loadEntries(reset: boolean, turn: number): Promise<void> {
    const reading = source;

    if (!reading) return;

    const query = search.value.trim();

    if (reset) {
      entries.loaded = [];
      entries.page = 0;
      entries.total = 0;
      entries.query = query;
    }

    const page = entries.page + 1;

    try {
      const result = await reading.entries({ q: entries.query, page, size: ENTRY_PAGE_SIZE });

      if (turn !== latest || entries.query !== query) return;

      allError.hidden = true;
      entries.loaded.push(...result.items);
      entries.page = page;
      entries.total = result.total;
      paintList();
    } catch (cause) {
      if (turn === latest) sayError(allError, cause);
    }
  }

  more.addEventListener('click', () => void loadEntries(false, latest));

  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  search.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => void loadEntries(true, latest), 250);
  });

  function clear(): void {
    latest++;
    opening++;
    source = null;
    section.hidden = true;
    error.hidden = true;
    line.hidden = true;
    featured.replaceChildren();
    all.hidden = true;
    list.replaceChildren();
    entries.loaded = [];
    entries.page = 0;
    entries.total = 0;
    entries.query = '';
    search.value = '';
    if (dialog.open) dialog.close();
  }

  return {
    open,

    hide: clear,

    async show(next, reader, isCurrent) {
      clear();

      const turn = latest;

      source = next;

      try {
        const preview = await next.preview();

        if (turn !== latest || !isCurrent()) return null;

        const said = previewLine(preview, reader);

        line.textContent = said ?? '';
        line.hidden = said === null;
        featured.replaceChildren(
          ...preview.entries.map((entry) => {
            const item = document.createElement('li');

            item.append(card(entry, () => turn === latest && isCurrent()));

            return item;
          }),
        );

        section.hidden = false;

        if (options.list && offersAllEntries(preview, reader)) {
          all.hidden = false;
          await loadEntries(true, turn);
        }

        return preview.preview;
      } catch (cause) {
        if (turn !== latest) return null;

        // Looking inside is a part of the page: its failure says so and leaves the rest.
        section.hidden = false;
        sayError(error, cause);

        return null;
      }
    },
  };
}
