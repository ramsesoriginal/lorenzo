// The Pictures pane (ADR 0255): the selected entry's picture, the one it shows from above when it
// has none of its own, a place to drop, paste or choose a new one (seen before it is sent), and an
// overview of the whole repository's pictures. Online only, like the picture in the entry pane.

import type { Bench } from '../core/bench';
import { PICTURE_TYPES, pictureSource } from '../core/pictures';

export interface PicturesUi {
  /** A file chosen but not yet sent, with the address of its preview. */
  staged: { entryId: string; file: File; url: string } | null;
  filter: 'all' | 'missing';
  /** Entries whose small picture has been asked for. */
  tried: Set<string>;
  /** How many tiles the overview shows. */
  shown: number;
  problem: string | null;
}
const TILES = 48;
export const newPicturesUi = (): PicturesUi => ({
  staged: null,
  filter: 'all',
  tried: new Set(),
  shown: TILES,
  problem: null,
});

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const button = (text: string, run: () => void, cls = 'btn') => {
  const b = el('button', cls, text);
  b.type = 'button';
  b.addEventListener('click', run);
  return b;
};

export function renderPictures(
  bench: Bench,
  id: string | null,
  ui: PicturesUi,
  hooks: { redraw: () => void; go: (id: string) => void },
): HTMLElement {
  const c = el('div', 'pane pane-pictures');
  const pictures = bench.pictures;
  const listing = bench.listing();
  const parentsOf = (x: string) => listing.find((e) => e.id === x)?.parentIds ?? [];
  const nameOf = (x: string) => listing.find((e) => e.id === x)?.name ?? x;

  if (id && bench.onServer(id)) {
    // This entry and what is above it, read for the picture it shows.
    const chain = [id];
    for (let i = 0; i < chain.length; i++)
      for (const p of parentsOf(chain[i] as string)) if (!chain.includes(p)) chain.push(p);
    for (const x of chain) if (bench.onServer(x)) void pictures.load(x);
  }

  const stage = (file: File | undefined) => {
    if (!id || !file) return;
    if (!PICTURE_TYPES.includes(file.type)) {
      ui.problem = 'Choose a PNG, JPEG, WebP or GIF picture.';
      return hooks.redraw();
    }
    if (ui.staged) URL.revokeObjectURL(ui.staged.url);
    ui.problem = null;
    ui.staged = { entryId: id, file, url: URL.createObjectURL(file) };
    hooks.redraw();
  };

  const here = el('section', 'pic-here');
  here.setAttribute('aria-label', 'Picture of the selected entry');
  if (!id) here.append(el('p', 'muted', 'Choose an entry in the explorer.'));
  else if (!bench.onServer(id))
    here.append(el('p', 'muted', 'A picture can be added once this entry has been sent.'));
  else {
    const source = pictureSource(parentsOf, (x) => pictures.get(x), id);
    const shownFrom = source.kind === 'inherited' ? source.from : id;
    const url = pictures.get(shownFrom);
    if (url) {
      const img = el('img', 'picture-img');
      img.src = url;
      img.alt = source.kind === 'inherited' ? `${nameOf(shownFrom)}'s picture` : 'Main picture';
      here.append(img);
    }
    const caption = el(
      'p',
      'pic-caption muted',
      source.kind === 'own'
        ? 'Its own picture.'
        : source.kind === 'inherited'
          ? `Shows ${nameOf(source.from)}'s picture, which it inherits.`
          : source.kind === 'none'
            ? 'No picture, and none above it.'
            : 'Looking for a picture…',
    );
    here.append(caption);

    const drop = el('div', 'pic-drop');
    drop.tabIndex = 0;
    drop.textContent = 'Drop a picture here, paste one, or choose a file.';
    drop.setAttribute('aria-label', 'Add a picture');
    drop.addEventListener('dragover', (e) => {
      e.preventDefault();
      drop.classList.add('over');
    });
    drop.addEventListener('dragleave', () => drop.classList.remove('over'));
    drop.addEventListener('drop', (e) => {
      e.preventDefault();
      stage(e.dataTransfer?.files[0]);
    });
    c.addEventListener('paste', (e) => {
      const file = [...(e.clipboardData?.files ?? [])].find((f) => f.type.startsWith('image/'));
      if (file) {
        e.preventDefault();
        stage(file);
      }
    });
    const input = el('input');
    input.type = 'file';
    input.accept = PICTURE_TYPES.join(',');
    input.hidden = true;
    input.setAttribute('aria-label', 'Picture file');
    input.addEventListener('change', () => stage(input.files?.[0]));
    const choose = button(
      source.kind === 'own'
        ? 'Replace picture…'
        : source.kind === 'inherited'
          ? 'Use its own picture…'
          : 'Choose picture…',
      () => input.click(),
    );
    here.append(drop, choose, input);
    if (source.kind === 'own') {
      const remove = button('Remove picture', () => void pictures.clear(id));
      remove.disabled = pictures.busy(id);
      here.append(remove);
    }

    if (ui.staged && ui.staged.entryId === id) {
      const staged = ui.staged;
      const box = el('div', 'pic-staged');
      box.setAttribute('role', 'group');
      box.setAttribute('aria-label', 'Picture to send');
      const img = el('img', 'picture-img');
      img.src = staged.url;
      img.alt = 'Preview of the new picture';
      const done = () => {
        URL.revokeObjectURL(staged.url);
        ui.staged = null;
      };
      box.append(
        img,
        el(
          'p',
          'muted',
          `${staged.file.name} · ${Math.max(1, Math.round(staged.file.size / 1024))} kB`,
        ),
        button(
          'Use this picture',
          async () => {
            const file = staged.file;
            done();
            await pictures.set(id, file);
            hooks.redraw();
          },
          'btn primary',
        ),
        button('Cancel', () => {
          done();
          hooks.redraw();
        }),
      );
      here.append(box);
    }
    const problem = ui.problem ?? pictures.problem(id);
    if (problem) {
      const p = el('p', 'bad', problem);
      p.setAttribute('role', 'alert');
      here.append(p);
    }
  }
  c.append(here);

  // The overview.
  const bar = el('div', 'pic-filter');
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', 'Which pictures');
  for (const [value, label] of [
    ['all', 'All pictures'],
    ['missing', 'Entries without their own'],
  ] as const) {
    const b = button(label, () => {
      ui.filter = value;
      ui.shown = TILES;
      hooks.redraw();
    });
    b.setAttribute('aria-pressed', String(ui.filter === value));
    bar.append(b);
  }
  c.append(bar);

  const fresh = listing
    .filter((e) => !ui.tried.has(e.id) && bench.onServer(e.id))
    .slice(0, ui.shown);
  if (fresh.length) {
    for (const e of fresh) ui.tried.add(e.id);
    void Promise.all(fresh.map((e) => pictures.quiet(e.id))).then(hooks.redraw);
  }
  const rows = listing
    .filter((e) => (ui.filter === 'all' ? true : pictures.get(e.id) === null))
    .sort((a, b) => a.name.localeCompare(b.name));
  const grid = el('ul', 'pic-grid');
  for (const e of rows.slice(0, ui.shown)) {
    const li = el('li');
    const tile = el('button', `pic-tile${e.id === id ? ' selected' : ''}`);
    tile.type = 'button';
    tile.dataset.pic = e.id;
    tile.addEventListener('click', () => hooks.go(e.id));
    const url = pictures.get(e.id);
    if (url) {
      const img = el('img');
      img.src = url;
      img.alt = '';
      tile.append(img);
    } else tile.append(el('span', 'pic-none', url === null ? 'No picture' : '…'));
    tile.append(el('span', 'pic-name', e.name));
    li.append(tile);
    grid.append(li);
  }
  if (!rows.length) grid.append(el('li', 'muted', 'Nothing to show.'));
  c.append(grid);
  if (rows.length > ui.shown)
    c.append(
      button(`Show more (${rows.length - ui.shown})`, () => {
        ui.shown += TILES;
        hooks.redraw();
      }),
    );
  return c;
}
