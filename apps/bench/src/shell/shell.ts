import type { EntryControls } from './entryControls';
// The workbench shell: draws a Workspace (workspace/model.ts) and turns pointer and keyboard
// input into changes to it. The layout rules live in the model; this file is the DOM.

import type { Bench } from '../core/bench';
import { canSetParents, type EntrySummary } from '../core/transport';
import { type HitResult, hitTest } from '../workspace/hit';
import {
  addTab,
  dockHome,
  emptyWorkspace,
  type Float,
  floatOut,
  type Group,
  group,
  type Home,
  layout,
  locate,
  move,
  moveFloat,
  normalize,
  parse,
  raise,
  removePane,
  resize,
  resizeFloat,
  type Side,
  serialize,
  setActive,
  showPane,
  splitGroup,
  treeGroups,
  type Workspace,
} from '../workspace/model';
import { neighbourGroup } from '../workspace/neighbour';
import {
  activePreset,
  applyPreset,
  PRESET_LABEL,
  PRESETS,
  type Preset,
} from '../workspace/presets';
import { renderAncestry } from './ancestryPane';
import {
  applySans,
  applyTheme,
  FACES,
  rememberSans,
  rememberTheme,
  savedSans,
  savedTheme,
  THEMES,
  type Theme,
  watchDevice,
} from './appearance';
import { openConflicts } from './conflictDialog';
import {
  kindsText,
  pictureSection,
  redraw,
  renderEntry,
  renderLinks,
  statusText,
} from './entryPane';
import {
  buildRows,
  counts,
  filterEntries,
  movedParents,
  moveTargets,
  ORDERS,
  type Order,
  parentOfKey,
} from './explorerRows';
import { type FormulaUi, newFormulaUi, renderFormulas } from './formulaPane';
import { type GridState, newGridState, renderGrid } from './gridPane';
import { type IconName, icon, kindIcon, LAYOUT_ICONS, paneIcon } from './icons';
import { focusing } from './linkPreview';
import { newPackUi, type PackUi, renderPack } from './packPane';
import { newPicturesUi, type PicturesUi, renderPictures } from './picturesPane';
import { renderStats } from './statsPane';
import { drawStatusBar } from './statusBar';
import { PANE_IDS, PANES } from './stub';
import { newVocabularyUi, renderVocabulary, type VocabularyUi } from './vocabularyPane';

const BAR = 30;
const STORE = 'bench:workspace';
const ORDER = 'bench:explorer-order';
/** The "Move to…" choice for no parent at all. */
const TOP = '__top';
const ORDER_ICON: Record<Order, IconName> = {
  inherits: 'ancestry',
  kind: 'kinds',
  name: 'sort',
};

const ORDER_LABEL: Record<Order, string> = {
  inherits: 'Inherits',
  kind: 'Kind',
  name: 'A to Z',
};

export function defaultWorkspace(): Workspace {
  const rail = group('g-rail', ['explorer']);
  const main = group('g-main', ['entry']);
  const right = group('g-right', ['props', 'links']);
  const tree = normalize({
    t: 's',
    id: 's-a',
    dir: 'row',
    ratios: [0.18, 0.56, 0.26],
    kids: [rail, main, right],
  });
  return { ...emptyWorkspace(), tree, next: 1 };
}

const el = <K extends keyof HTMLElementTagNameMap>(
  tag: K,
  cls?: string,
  text?: string,
): HTMLElementTagNameMap[K] => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

type Command = { label: string; run: () => void; icon?: IconName };

const titleOf = (id: string) => PANES.find((p) => p.id === id)?.title ?? id;

export class Shell {
  ws: Workspace;
  home: Home = {};
  selected: string | null = null;
  focus = 'entry';
  private root: HTMLElement;
  private surface = el('div', 'surface');
  private overlay = el('div', 'drop');
  private ghost = el('div', 'ghost');
  private mark = el('div', 'mark');
  private drag: null | {
    kind: 'tab' | 'float';
    gid: string;
    panes: string[];
    active: string;
    sx: number;
    sy: number;
    ox: number;
    oy: number;
    started: boolean;
    fx: number;
    fy: number;
    hit: HitResult | null;
    label: string;
  } = null;
  private palette: HTMLElement | null = null;
  /** The Write / Inspect / Compare switch; the page puts it in the title bar. */
  readonly layoutEl = el('div', 'layouts');
  private readonly announceEl = el('div', 'sr-only');
  readonly statusEl = el('footer', 'statusbar');
  /** What the Table and the Compare grid keep while the page is drawn again. */
  private packUi: PackUi = newPackUi();
  private picturesUi: PicturesUi = newPicturesUi();
  private newOpen = false;
  private formulaUi: FormulaUi = newFormulaUi();
  private vocabularyUi: VocabularyUi = newVocabularyUi();
  private grids: Record<'table' | 'grid', GridState> = {
    table: newGridState(),
    grid: newGridState(),
  };
  /** How the explorer lists entries, and which entries in the tree are folded shut. */
  private order: Order = Shell.savedOrder();
  private collapsed = new Set<string>();
  /** What is typed in the explorer's filter: entries with a name that has it are listed. */
  private filter = '';
  /** Commands the page adds to the palette, such as switching repository. */
  extra: Command[] = [];

  private unsubscribe: (() => void) | null = null;
  private entryControls: EntryControls | undefined;

  constructor(
    root: HTMLElement,
    public bench: Bench,
  ) {
    this.root = root;
    let saved: Workspace | null = null;
    try {
      saved = parse(localStorage.getItem(STORE), PANE_IDS);
    } catch {
      saved = null;
    }
    this.ws = saved ?? defaultWorkspace();
    applyTheme(savedTheme());
    applySans(savedSans());
    watchDevice();
    this.announceEl.setAttribute('role', 'status');
    this.announceEl.setAttribute('aria-live', 'polite');
    root.append(this.surface, this.overlay, this.ghost, this.mark, this.announceEl);
    this.overlay.hidden = this.ghost.hidden = this.mark.hidden = true;
    window.addEventListener('pointermove', (e) => this.onMove(e));
    window.addEventListener('pointerup', (e) => this.onUp(e));
    window.addEventListener('keydown', (e) => this.onKey(e));
    this.watchPending();
    this.unsubscribe = bench.subscribe((background) => (background ? this.later() : this.render()));
    this.unsubscribePictures = bench.subscribePictures(() => this.pictureChanged());
    this.unsubscribeConnections = bench.subscribeConnections(() => this.refreshPane('links'));
    this.render();
  }

  private unsubscribeConnections: (() => void) | null = null;

  /** Makes one pane again on its own, where it is showing (what is written elsewhere is left alone). */
  private refreshPane(id: string) {
    const now = this.root.querySelector(`.pane-${id}`);
    if (now) now.replaceWith(this.paneEl(id));
  }

  private unsubscribePictures: (() => void) | null = null;

  /**
   * A picture was read, set or taken away. Where it shows next to the entry, that part is made
   * again on its own, so what is being written in the entry is left alone; panes that list pictures
   * are drawn again.
   */
  private pictureChanged() {
    if (this.root.querySelector('.pane-pictures')) return this.later();
    const id = this.selected;
    const now = this.root.querySelector('.pane-entry .picture');
    if (id && now) now.replaceWith(pictureSection(this.bench, id));
  }

  /** Hands the shell the bench to show, once the session has said which repository it is. */
  use(bench: Bench, controls?: EntryControls) {
    this.entryControls = controls;
    this.unsubscribe?.();
    this.unsubscribePictures?.();
    this.unsubscribeConnections?.();
    this.bench = bench;
    this.selected = null;
    this.unsubscribe = bench.subscribe((background) => (background ? this.later() : this.render()));
    this.unsubscribePictures = bench.subscribePictures(() => this.pictureChanged());
    this.unsubscribeConnections = bench.subscribeConnections(() => this.refreshPane('links'));
    this.render();
  }

  // ---- state ----------------------------------------------------------------------------------

  private set(ws: Workspace, home?: Home) {
    this.ws = ws;
    if (home) this.home = home;
    try {
      localStorage.setItem(STORE, serialize(ws));
    } catch {
      /* private window or blocked storage: the layout is just not remembered */
    }
    this.render();
  }

  /** The theme the reader chose, and what it is for the text: kept by `appearance`. */
  theme(): Theme {
    return savedTheme();
  }

  setTheme(t: Theme) {
    rememberTheme(t);
    applyTheme(t);
  }

  sans(): boolean {
    return savedSans();
  }

  setSans(on: boolean) {
    rememberSans(on);
    applySans(on);
  }

  select(id: string) {
    this.selected = id;
    // The explorer shows where the entry is, once: the first place it is listed.
    this.reveal = { id, until: Date.now() + 3000 };
    for (const a of this.ancestorsOf(id)) this.collapsed.delete(a);
    void this.bench.open(id);
    this.set(showPane(this.ws, 'entry'));
  }

  /** The entry just chosen, which the explorer scrolls to once its own controls are in place. */
  private reveal: { id: string; until: number } | null = null;

  /** What the entry inherits from, all the way up (so the explorer can open the way to it). */
  private ancestorsOf(id: string): string[] {
    const parents = new Map(this.bench.listing().map((e) => [e.id, e.parentIds]));
    const out: string[] = [];
    const walk = (x: string) => {
      for (const p of parents.get(x) ?? [])
        if (!out.includes(p)) {
          out.push(p);
          walk(p);
        }
    };
    walk(id);
    return out;
  }

  open(pane: string) {
    this.focus = pane;
    this.set(showPane(this.ws, pane));
  }

  /** Arranges the panes as a preset (Write, Inspect, Compare). */
  layout(name: Preset) {
    this.set(applyPreset(this.ws, name));
  }

  private drawLayouts() {
    const now = activePreset(this.ws);
    this.layoutEl.setAttribute('role', 'group');
    this.layoutEl.setAttribute('aria-label', 'Layout');
    this.layoutEl.replaceChildren(
      ...PRESETS.map((p) => {
        const b = el('button', 'btn');
        b.append(icon(LAYOUT_ICONS[p], 14), document.createTextNode(PRESET_LABEL[p]));
        b.type = 'button';
        b.setAttribute('aria-pressed', String(p === now));
        b.addEventListener('click', () => this.layout(p));
        return b;
      }),
    );
  }

  reset() {
    this.home = {};
    this.set(defaultWorkspace());
  }

  // ---- drawing --------------------------------------------------------------------------------

  /**
   * Draws the page once, after what is running now, however many changes come before then. It is a
   * microtask, not a frame: the page is as it should be before anything else (a click, a test)
   * looks at it, and a burst of changes in one go is still one drawing.
   */
  private later() {
    if (this.pending) return;
    this.pending = true;
    queueMicrotask(() => {
      if (!this.pending) return;
      this.render();
    });
  }
  private pending = false;

  /**
   * A field that was typed in when the page was drawn again keeps its text but starts over as to
   * what counts as changed: Enter or leaving it would make no change. So a field put back with
   * something typed in it says "change" itself when it is left or Enter is pressed.
   */
  private watchPending() {
    const settle = (e: Event) => {
      const t = e.target;
      if (!(t instanceof HTMLInputElement) || t.dataset.pending !== '1') return;
      delete t.dataset.pending;
      t.dispatchEvent(new Event('change', { bubbles: true }));
    };
    window.addEventListener('keydown', (e) => e.key === 'Enter' && settle(e), true);
    window.addEventListener('focusout', settle, true);
    // The field's own change says it is settled.
    window.addEventListener(
      'change',
      (e) => {
        if (e.isTrusted && e.target instanceof HTMLElement) delete e.target.dataset.pending;
      },
      true,
    );
  }

  private render() {
    this.pending = false;
    const s = this.surface;
    // Keep what a person is typing when something else changes the page.
    const active = document.activeElement;
    const typing = active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement;
    const kept =
      active instanceof HTMLElement && active.dataset.key && s.contains(active)
        ? {
            key: active.dataset.key,
            // Only a field has what is typed in it; a link is only found again.
            value: typing ? active.value : null,
            at: typing ? active.selectionStart : null,
            to: typing ? active.selectionEnd : null,
          }
        : null;
    this.drawLayouts();
    // Write is for writing: the page says so, and what is not the text steps back (see bench.css).
    this.root.dataset.layout = activePreset(this.ws) ?? '';
    drawStatusBar(this.statusEl, this.bench, this.selected, () =>
      openConflicts(this.bench, (x) => this.select(x)),
    );
    // What was scrolled stays where it was: the page is made again, the reader's place is not lost.
    const scrolls = new Map<string, number>();
    for (const e of s.querySelectorAll<HTMLElement>(SCROLLERS))
      if (e.scrollTop) scrolls.set(scrollKey(e), e.scrollTop);
    redraw.active = true;
    s.replaceChildren();
    redraw.active = false;
    const L = layout(this.ws.tree);
    for (const q of L.groups)
      s.append(this.groupEl(q.g, false, { l: q.x, t: q.y, w: q.w, h: q.h }));
    for (const d of L.splits) s.append(this.dividerEl(d));
    for (const f of this.ws.floats) s.append(this.groupEl(f, true));
    if (!L.groups.length && !this.ws.floats.length) {
      const empty = el('div', 'empty', 'Nothing open. Press Ctrl+K to open something.');
      s.append(empty);
    }
    for (const e of s.querySelectorAll<HTMLElement>(SCROLLERS)) {
      const at = scrolls.get(scrollKey(e));
      if (at !== undefined) e.scrollTop = at;
    }
    // Only a choice moves the explorer: to where the entry is first listed (and not at all if it
    // is in view).
    if (this.reveal && (this.bench.view(this.reveal.id) || Date.now() > this.reveal.until)) {
      // (After the entry has been read: what shows for it moves the list a little.)
      s.querySelector(`.pane-explorer [data-entry="${this.reveal.id}"]`)?.scrollIntoView({
        block: 'nearest',
      });
      this.reveal = null;
    }
    if (kept) {
      focusing.restoring = true;
      const found = s.querySelector<HTMLElement>(`[data-key="${kept.key}"]`);
      if (found instanceof HTMLInputElement || found instanceof HTMLTextAreaElement) {
        if (kept.value !== null) {
          if (found instanceof HTMLInputElement && found.value !== kept.value)
            found.dataset.pending = '1';
          found.value = kept.value;
        }
        found.dispatchEvent(new Event('input')); // the preview follows what is typed
        found.focus({ preventScroll: true });
        if (kept.at !== null) found.setSelectionRange(kept.at, kept.to ?? kept.at);
      } else found?.focus({ preventScroll: true });
      focusing.restoring = false;
    }
  }

  private groupEl(
    g: Group | Float,
    floating: boolean,
    pct?: { l: number; t: number; w: number; h: number },
  ) {
    const box = el('section', floating ? 'grp float' : 'grp');
    box.dataset.grp = g.id;
    if (pct) {
      box.style.left = `${pct.l * 100}%`;
      box.style.top = `${pct.t * 100}%`;
      box.style.width = `${pct.w * 100}%`;
      box.style.height = `${pct.h * 100}%`;
    } else {
      const f = g as Float;
      box.style.left = `${f.x}px`;
      box.style.top = `${f.y}px`;
      box.style.width = `${f.w}px`;
      box.style.height = `${f.h}px`;
      box.addEventListener('pointerdown', () => {
        if (this.ws.floats[this.ws.floats.length - 1]?.id !== g.id) this.set(raise(this.ws, g.id));
      });
    }
    const bar = el('div', 'bar');
    bar.dataset.gtabs = g.id;
    bar.style.height = `${BAR}px`;
    if (g.panes.length === 1 && !floating) {
      // One tab: a title line, not a strip.
      bar.classList.add('solo');
    }
    for (const p of g.panes) bar.append(this.tabEl(g, p, floating));
    if (!floating) {
      const out = el('button', 'icon');
      out.append(icon('float', 14));
      out.type = 'button';
      out.title = `Open ${titleOf(g.active)} in its own window`;
      out.setAttribute('aria-label', `Float ${titleOf(g.active)}`);
      out.addEventListener('click', () => this.floatPane(g.active));
      out.addEventListener('pointerdown', (e) => e.stopPropagation());
      bar.append(el('span', 'grow'), out);
    }
    if (floating) {
      const dock = el('button', 'icon');
      dock.append(icon('dock', 14), document.createTextNode('Dock'));
      dock.title = 'Dock this window';
      dock.addEventListener('click', () => this.dock(g.id));
      dock.addEventListener('pointerdown', (e) => e.stopPropagation());
      bar.append(el('span', 'grow'), dock);
      bar.addEventListener('pointerdown', (e) => {
        if (e.button !== 0 || (e.target as HTMLElement).closest('.tab, .icon')) return;
        this.startDrag(e, 'float', g, g.panes, g.active, bar);
      });
    }
    const body = el('div', 'body');
    body.append(this.paneEl(g.active));
    box.append(bar, body);
    if (floating) {
      const grip = el('div', 'grip');
      grip.addEventListener('pointerdown', (e) => this.startResizeFloat(e, g as Float));
      box.append(grip);
    }
    return box;
  }

  private tabEl(g: Group, p: string, floating: boolean) {
    const t = el('div', p === g.active ? 'tab on' : 'tab');
    t.dataset.tab = p;
    const b = el('button', 'name');
    const pi = paneIcon(p);
    if (pi) b.append(icon(pi, 14));
    b.append(document.createTextNode(titleOf(p)));
    if (p === 'links') {
      // How many parents and children the selected entry has.
      const n = this.selected ? this.bench.linkCount(this.selected) : 0;
      if (n) {
        const badge = el('span', 'badge', String(n));
        badge.setAttribute('aria-label', `${n} links`);
        b.append(' ', badge);
      }
    }
    b.type = 'button';
    // Found again when the page is drawn again, so the focus is put back on it.
    b.dataset.key = `tab:${p}`;
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(p === g.active));
    b.addEventListener('click', () => {
      this.focus = p;
      this.set(setActive(this.ws, g.id, p));
    });
    b.addEventListener('keydown', (e) => this.onTabKey(e, g, p));
    const x = el('button', 'x');
    x.append(icon('close', 13));
    x.type = 'button';
    x.title = `Close ${titleOf(p)}`;
    x.setAttribute('aria-label', `Close ${titleOf(p)}`);
    x.addEventListener('click', () => this.set(removePane(this.ws, p)));
    t.append(b, x);
    t.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || (e.target as HTMLElement).closest('.x')) return;
      this.startDrag(e, 'tab', g, [p], p, t);
    });
    void floating;
    return t;
  }

  private dividerEl(d: ReturnType<typeof layout>['splits'][number]) {
    const e = el('div', `divider divider-${d.dir}`);
    e.style.left = `${d.rect.x * 100}%`;
    e.style.top = `${d.rect.y * 100}%`;
    if (d.dir === 'row') e.style.height = `${d.rect.h * 100}%`;
    else e.style.width = `${d.rect.w * 100}%`;
    e.addEventListener('pointerdown', (ev) => this.startResize(ev, d));
    return e;
  }

  private static savedOrder(): Order {
    try {
      const saved = localStorage.getItem(ORDER);
      return ORDERS.find((o) => o === saved) ?? 'inherits';
    } catch {
      return 'inherits';
    }
  }

  private setOrder(order: Order) {
    this.order = order;
    try {
      localStorage.setItem(ORDER, order);
    } catch {
      /* not remembered */
    }
    this.render();
  }

  /** The entries, as a tree of what they inherit from, by kind, or A to Z. */
  private explorerList(): HTMLElement {
    const bench = this.bench;
    const box = el('div', 'explorer');
    const all = bench.listing();
    const filtering = this.filter.trim() !== '';
    // A filter lists what matches, flat and by name: where an entry sits matters less than finding it.
    const matches = filterEntries(all, this.filter);
    const rows = buildRows(matches, filtering ? 'name' : this.order, this.collapsed);
    const n = counts(rows);

    const search = el('input', 'explorer-filter');
    search.type = 'search';
    search.placeholder = 'Filter entries';
    search.value = this.filter;
    search.dataset.key = 'explorer-filter';
    search.setAttribute('aria-label', 'Filter entries');
    search.addEventListener('input', () => {
      // The redraw puts the typed text back and says "input" again: that is not a change.
      if (search.value === this.filter) return;
      this.filter = search.value;
      this.render();
    });
    search.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && this.filter) {
        ev.stopPropagation();
        // The redraw keeps what is in the field, so the field is emptied first.
        search.value = '';
        this.filter = '';
        this.render();
      }
    });
    const wrap = el('label', 'rsearch');
    wrap.append(icon('search', 15), search);
    box.append(wrap);

    const head = el('div', 'explorer-head');
    head.append(
      el(
        'span',
        'muted',
        filtering
          ? `${n.entries} of ${all.length} entries`
          : n.places > n.entries
            ? `${n.entries} entries`
            : `${n.entries} entries`,
      ),
      el('span', 'grow'),
    );
    const add = el('button', 'btn quiet new-btn');
    add.type = 'button';
    add.append(icon('add', 14), document.createTextNode(' New'));
    add.setAttribute('aria-expanded', String(this.newOpen));
    add.addEventListener('click', () => {
      this.newOpen = !this.newOpen;
      if (!this.newOpen) this.newEntryDraft = null;
      this.render();
    });
    head.append(add);
    const seg = el('div', 'seg');
    seg.setAttribute('role', 'group');
    seg.setAttribute('aria-label', 'Order');
    for (const o of ORDERS) {
      const b = el('button', 'btn');
      b.append(icon(ORDER_ICON[o], 14), document.createTextNode(ORDER_LABEL[o]));
      b.type = 'button';
      b.setAttribute('aria-pressed', String(o === this.order));
      b.addEventListener('click', () => this.setOrder(o));
      seg.append(b);
    }
    box.append(head);
    if (this.newOpen) box.append(this.newEntryForm());
    box.append(seg);
    const move = this.moveControl();
    if (move) box.append(move);
    if (filtering && !rows.length)
      box.append(el('p', 'muted pad', 'No entry matches that filter.'));

    const list = el('ul', 'list');
    const byId = new Map(all.map((x) => [x.id, x]));
    if (this.order === 'inherits' && !filtering) this.dropOnList(list, byId);
    for (const row of rows) {
      const li = el('li', row.type === 'header' ? 'group-head' : 'place');
      if (row.type === 'header') {
        li.textContent = row.label;
        list.append(li);
        continue;
      }
      const e = byId.get(row.id);
      if (!e) continue;
      li.style.paddingLeft = `${row.depth * 14}px`;
      if (this.order === 'inherits' && !filtering) {
        if (row.hasChildren) {
          const fold = el('button', 'fold');
          fold.append(icon(row.open ? 'expand' : 'next', 13));
          fold.type = 'button';
          fold.setAttribute('aria-label', `${row.open ? 'Fold' : 'Unfold'} ${e.name}`);
          fold.setAttribute('aria-expanded', String(row.open));
          fold.addEventListener('click', () => {
            if (this.collapsed.has(row.id)) this.collapsed.delete(row.id);
            else this.collapsed.add(row.id);
            this.render();
          });
          li.append(fold);
        } else li.append(el('span', 'fold'));
      }
      const b = el('button', row.id === this.selected ? 'row on' : 'row');
      b.append(icon(kindIcon(e.kinds), 15), el('span', 'nm', e.name));
      b.type = 'button';
      b.dataset.entry = row.id;
      b.dataset.place = row.key;
      b.title = bench.status(row.id) === 'synced' ? kindsText(e.kinds) : statusText(bench, row.id);
      b.addEventListener('click', () => this.select(row.id));
      li.append(b);
      if (this.order === 'inherits' && !filtering) this.dragRow(li, b, row.id, row.key, byId);
      if (row.parentCount) {
        const multi = el('span', 'multi');
        multi.append(icon('ancestry', 13));
        multi.title = `Has ${row.parentCount} parents: it is in each of those places`;
        multi.setAttribute('role', 'img');
        multi.setAttribute('aria-label', `Has ${row.parentCount} parents`);
        li.append(multi);
      }
      list.append(li);
    }
    box.append(list);
    return box;
  }

  /** What is being dragged in the tree: the entry, and the entry it hangs under in that row. */
  private dragging: { id: string; from: string | null } | null = null;

  /** Can the dragged entry be dropped under `target` (null: the top level)? Its new parents, if so. */
  private dropParents(
    byId: ReadonlyMap<string, EntrySummary>,
    target: string | null,
  ): string[] | null {
    const d = this.dragging;
    const item = d ? byId.get(d.id) : null;
    if (!d || !item) return null;
    if (target !== null && !moveTargets(this.bench.listing(), d.id).some((e) => e.id === target))
      return null;
    return movedParents(item.parentIds, d.from, target);
  }

  private drop(byId: ReadonlyMap<string, EntrySummary>, target: string | null) {
    const parents = this.dropParents(byId, target);
    const d = this.dragging;
    this.dragging = null;
    // The entry may not have been opened yet: a command needs its loaded form.
    if (parents && d)
      void this.bench.open(d.id).then(() => this.bench.change('entry.set-parents', d.id, parents));
  }

  /** A row is dragged by its name and dropped on another row, which it then hangs under. */
  private dragRow(
    li: HTMLElement,
    b: HTMLElement,
    id: string,
    key: string,
    byId: ReadonlyMap<string, EntrySummary>,
  ) {
    const item = byId.get(id);
    if (item && canSetParents(item.kinds)) {
      b.draggable = true;
      b.addEventListener('dragstart', (e) => {
        this.dragging = { id, from: parentOfKey(key) };
        e.dataTransfer?.setData('text/plain', id);
        if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
        li.closest('.list')?.classList.add('dragging');
      });
      b.addEventListener('dragend', () => {
        this.dragging = null;
        li.closest('.list')?.classList.remove('dragging');
        for (const x of document.querySelectorAll('.drop-on')) x.classList.remove('drop-on');
      });
    }
    li.addEventListener('dragover', (e) => {
      if (!this.dropParents(byId, id)) return;
      e.preventDefault();
      e.stopPropagation();
      li.classList.add('drop-on');
    });
    li.addEventListener('dragleave', () => li.classList.remove('drop-on'));
    li.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      li.classList.remove('drop-on');
      this.drop(byId, id);
    });
  }

  /** Dropping on the list outside any row takes the entry out of the place it was dragged from. */
  private dropOnList(list: HTMLElement, byId: ReadonlyMap<string, EntrySummary>) {
    list.addEventListener('dragover', (e) => {
      if (!this.dropParents(byId, null)) return;
      e.preventDefault();
      list.classList.add('drop-top');
    });
    list.addEventListener('dragleave', (e) => {
      if (e.target === list) list.classList.remove('drop-top');
    });
    list.addEventListener('drop', (e) => {
      e.preventDefault();
      list.classList.remove('drop-top');
      this.drop(byId, null);
    });
  }

  /**
   * "Move to…" for the selected entry: it makes the chosen entry its only parent (or none, at the
   * top level), as one change. Which entries it can go under leaves out itself and what is under it.
   */
  private moveControl(): HTMLElement | null {
    const id = this.selected;
    const item = id ? this.bench.view(id) : null;
    if (!id || !item || !canSetParents(item.kinds)) return null;
    const select = el('select', 'explorer-move');
    select.setAttribute('aria-label', 'Move to…');
    select.append(new Option('Move to…', ''));
    if (item.parentIds.length) select.append(new Option('Top level (no parent)', TOP));
    for (const e of moveTargets(this.bench.listing(), id))
      if (!(item.parentIds.length === 1 && item.parentIds[0] === e.id))
        select.append(new Option(e.name, e.id));
    select.addEventListener('change', () => {
      if (!select.value) return;
      this.bench.change('entry.set-parents', id, select.value === TOP ? [] : [select.value]);
    });
    return select;
  }

  private paneEl(id: string): HTMLElement {
    const bench = this.bench;
    if (id === 'entry')
      return renderEntry(bench, this.selected, (x) => this.select(x), this.entryControls);
    if (id === 'props') return renderStats(bench, this.selected);
    if (id === 'links') return renderLinks(bench, this.selected, (x) => this.select(x));
    if (id === 'ancestry') return renderAncestry(bench, this.selected, (x) => this.select(x));
    if (id === 'pack')
      return renderPack(bench, this.selected, this.packUi, {
        redraw: () => this.render(),
        go: (x) => this.select(x),
      });
    if (id === 'pictures')
      return renderPictures(bench, this.selected, this.picturesUi, {
        redraw: () => this.render(),
        go: (x) => this.select(x),
      });
    if (id === 'formula')
      return renderFormulas(bench, this.selected, this.formulaUi, {
        redraw: () => this.render(),
        go: (x) => this.select(x),
      });
    if (id === 'vocabulary') return renderVocabulary(bench, this.vocabularyUi, () => this.render());
    if (id === 'table' || id === 'grid')
      return renderGrid(bench, this.grids[id], {
        compact: id === 'table',
        redraw: () => this.render(),
        go: (x) => this.select(x),
        openGrid: () => this.open('grid'),
      });
    const c = el('div', `pane pane-${id}`);
    if (id === 'explorer') {
      if (bench.loadError && !bench.entries.length) c.append(el('p', 'bad', bench.loadError));
      c.append(this.explorerList());
    }
    return c;
  }

  /** Name, kind and parent of an entry to make; it shows in the list at once. */
  private newEntryDraft: { name: string; kind: string; parent: string } | null = null;
  private newEntryForm(): HTMLElement {
    this.newEntryDraft ??= { name: '', kind: 'item', parent: this.selected ?? '' };
    const draft = this.newEntryDraft;
    const bench = this.bench;
    const form = el('form', 'new-entry');
    const name = el('input');
    name.type = 'text';
    name.placeholder = 'New entry';
    name.value = draft.name;
    name.addEventListener('input', () => {
      draft.name = name.value;
    });
    name.dataset.key = 'new-entry-name';
    name.setAttribute('aria-label', 'Name of the new entry');
    const kind = el('select');
    kind.setAttribute('aria-label', 'Kind of the new entry');
    for (const [value, label] of [
      ['item', 'Item'],
      ['being', 'Being'],
      ['fact', 'Fact'],
      ['item,being', 'Item and being'],
      ['', 'Bare entry'],
    ] as const)
      kind.append(new Option(label, value));
    kind.value = draft.kind;
    kind.addEventListener('change', () => {
      draft.kind = kind.value;
    });
    const parent = el('select');
    parent.setAttribute('aria-label', 'Parent of the new entry');
    parent.append(new Option('No parent', ''));
    for (const e of bench.listing())
      parent.append(new Option(e.name, e.id, false, e.id === draft.parent));
    parent.value = draft.parent;
    parent.addEventListener('change', () => {
      draft.parent = parent.value;
    });
    const add = el('button', 'btn', 'Add');
    add.type = 'submit';
    form.append(name, kind, parent, add);
    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const text = name.value.trim();
      if (!text) return;
      this.newEntryDraft = null;
      const id = bench.create({
        name: text,
        kinds: kind.value ? kind.value.split(',') : [],
        parents: parent.value ? [parent.value] : [],
      });
      name.value = '';
      this.newEntryDraft = null;
      this.select(id);
    });
    return form;
  }

  // ---- pointer --------------------------------------------------------------------------------

  private rect() {
    return this.surface.getBoundingClientRect();
  }

  private startDrag(
    e: PointerEvent,
    kind: 'tab' | 'float',
    g: Group,
    panes: string[],
    active: string,
    from: HTMLElement,
  ) {
    const r = this.rect();
    const b = from.getBoundingClientRect();
    const f = g as Float;
    this.drag = {
      kind,
      gid: g.id,
      panes,
      active,
      sx: e.clientX,
      sy: e.clientY,
      ox: e.clientX - r.left - (kind === 'float' ? f.x : 0),
      oy: e.clientY - r.top - (kind === 'float' ? f.y : 0),
      started: false,
      fx: kind === 'float' ? f.x : b.left - r.left,
      fy: kind === 'float' ? f.y : b.top - r.top,
      hit: null,
      label: panes.map(titleOf).join(', '),
    };
  }

  private startResize(e: PointerEvent, d: ReturnType<typeof layout>['splits'][number]) {
    e.preventDefault();
    const r = this.rect();
    const total = d.dir === 'row' ? r.width * d.nodeRect.w : r.height * d.nodeRect.h;
    let last = d.dir === 'row' ? e.clientX : e.clientY;
    const move = (ev: PointerEvent) => {
      const cur = d.dir === 'row' ? ev.clientX : ev.clientY;
      const delta = (cur - last) / total;
      last = cur;
      // Re-render per step; the model clamps the pair at its minimum.
      this.ws = resize(this.ws, d.sid, d.i, delta);
      this.render();
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      this.set(this.ws);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  private startResizeFloat(e: PointerEvent, f: Float) {
    e.preventDefault();
    e.stopPropagation();
    const sx = e.clientX;
    const sy = e.clientY;
    const move = (ev: PointerEvent) => {
      this.ws = resizeFloat(
        this.ws,
        f.id,
        Math.max(200, f.w + ev.clientX - sx),
        Math.max(120, f.h + ev.clientY - sy),
      );
      this.render();
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      this.set(this.ws);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  private tabSlot = (gid: string, clientX: number) => {
    const r = this.rect();
    const tabs = this.surface.querySelectorAll<HTMLElement>(`[data-gtabs="${gid}"] [data-tab]`);
    let idx = tabs.length;
    let x: number | null = null;
    for (let i = 0; i < tabs.length; i++) {
      const b = tabs[i].getBoundingClientRect();
      if (x === null) x = b.left;
      if (clientX < b.left + b.width / 2) {
        idx = i;
        x = b.left;
        break;
      }
      x = b.right;
    }
    return { idx, x: (x ?? 0) - r.left };
  };

  private onMove(e: PointerEvent) {
    const d = this.drag;
    if (!d) return;
    if (!d.started) {
      if (Math.abs(e.clientX - d.sx) + Math.abs(e.clientY - d.sy) < 6) return;
      d.started = true;
      this.ghost.textContent = d.label;
      this.root.classList.add('dragging');
    }
    const r = this.rect();
    const px = e.clientX - r.left;
    const py = e.clientY - r.top;
    if (d.kind === 'float') {
      d.fx = px - d.ox;
      d.fy = py - d.oy;
      const box = this.surface.querySelector<HTMLElement>(`[data-grp="${d.gid}"]`);
      if (box) {
        box.style.left = `${d.fx}px`;
        box.style.top = `${d.fy}px`;
      }
    } else {
      this.ghost.hidden = false;
      this.ghost.style.left = `${px + 14}px`;
      this.ghost.style.top = `${py + 14}px`;
    }
    d.hit = hitTest(
      this.ws,
      px,
      py,
      { w: r.width, h: r.height },
      d,
      () => BAR,
      e.clientX,
      this.tabSlot,
    );
    this.showHit(d.hit);
  }

  private showHit(h: HitResult | null) {
    if (!h) {
      this.overlay.hidden = this.mark.hidden = true;
      return;
    }
    const { rect, hint, markX } = h;
    const o = this.overlay;
    o.hidden = false;
    let { x, y, w, h: hh } = rect;
    if (hint.zone === 'left') w /= 2;
    else if (hint.zone === 'right') {
      x += w / 2;
      w /= 2;
    } else if (hint.zone === 'top') hh /= 2;
    else if (hint.zone === 'bottom') {
      y += hh / 2;
      hh /= 2;
    }
    o.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${hh}px`;
    this.mark.hidden = markX === null;
    if (markX !== null) this.mark.style.cssText = `left:${markX}px;top:${rect.y}px;height:${BAR}px`;
  }

  private onUp(_e: PointerEvent) {
    const d = this.drag;
    if (!d) return;
    this.drag = null;
    this.root.classList.remove('dragging');
    this.ghost.hidden = this.overlay.hidden = this.mark.hidden = true;
    if (!d.started) return;
    // The click that follows a drag must not also activate a tab.
    const swallow = (ev: Event) => ev.stopPropagation();
    window.addEventListener('click', swallow, { capture: true, once: true });
    setTimeout(() => window.removeEventListener('click', swallow, true), 0);
    const r = this.rect();
    if (d.hit) {
      const out = move(this.ws, d.panes, d.active, d.hit.hint, d.gid, this.home);
      this.set(out.ws, out.home);
    } else if (d.kind === 'float') {
      const f = this.ws.floats.find((x) => x.id === d.gid);
      const x = Math.max(-(f?.w ?? 0) + 80, Math.min(r.width - 80, d.fx));
      const y = Math.max(0, Math.min(r.height - BAR, d.fy));
      this.set(moveFloat(this.ws, d.gid, x, y));
    } else {
      this.floatTab(
        d.panes,
        d.active,
        Math.max(8, Math.min(r.width - 200, d.fx)),
        Math.max(8, Math.min(r.height - 80, d.fy)),
      );
    }
  }

  // ---- window and tab commands (used by pointer, keyboard and palette) -------------------------

  private floatTab(panes: string[], active: string, x: number, y: number) {
    const def = PANES.find((p) => p.id === panes[0]);
    const out = floatOut(this.ws, panes, active, x, y, this.home, def?.float);
    this.set(out.ws, out.home);
  }

  floatPane(pane: string) {
    const loc = locate(this.ws, pane);
    if (!loc || loc.kind === 'float') return;
    const n = this.ws.floats.length;
    // Placed so the window fits inside the page, whatever its width.
    const w = PANES.find((p) => p.id === pane)?.float[0] ?? 460;
    this.floatTab([pane], pane, Math.max(8, this.rect().width - w - 16 - n * 28), 48 + n * 28);
  }

  dock(gid: string) {
    const f = this.ws.floats.find((x) => x.id === gid);
    if (!f) return;
    let ws = this.ws;
    for (const p of f.panes) ws = removePane(ws, p);
    this.set(dockHome(ws, f.panes, f.active, this.home, 'entry'));
  }

  splitPane(pane: string, side: Side) {
    const loc = locate(this.ws, pane);
    if (!loc || loc.kind !== 'tree') return;
    const g = treeGroups(this.ws.tree).find((x) => x.id === loc.gid);
    if (!g || g.panes.length < 2) return;
    const ws = splitGroup(removePaneKeepGroup(this.ws, g.id, pane), g.id, side, [pane], pane);
    this.set(ws);
  }

  // ---- keyboard -------------------------------------------------------------------------------

  /** Tabs are keyboard-reachable: Alt+arrows reorder, Alt+Shift+arrows split, Alt+F floats. */
  private onTabKey(e: KeyboardEvent, g: Group, p: string) {
    if (!e.altKey) {
      // Arrows go between the tabs of a group (and choose the one they reach); Home and End go to the ends.
      const at = g.panes.indexOf(p);
      const to =
        e.key === 'ArrowLeft'
          ? at - 1
          : e.key === 'ArrowRight'
            ? at + 1
            : e.key === 'Home'
              ? 0
              : e.key === 'End'
                ? g.panes.length - 1
                : -1;
      const next = g.panes[to];
      if (e.ctrlKey || e.metaKey || e.shiftKey || !next) return;
      e.preventDefault();
      this.focus = next;
      this.set(setActive(this.ws, g.id, next));
      this.root.querySelector<HTMLElement>(`[data-tab="${next}"] .name`)?.focus();
      return;
    }
    const sides: Record<string, Side> = {
      ArrowLeft: 'left',
      ArrowRight: 'right',
      ArrowUp: 'top',
      ArrowDown: 'bottom',
    };
    if (e.key === 'f' || e.key === 'F') {
      e.preventDefault();
      this.floatPane(p);
      this.say(`${titleOf(p)} is in its own window.`);
    } else if (e.key === 'd' || e.key === 'D') {
      const loc = locate(this.ws, p);
      if (loc?.kind !== 'float') return;
      e.preventDefault();
      this.dock(loc.gid);
      this.say(`${titleOf(p)} is back in the workbench.`);
    } else if (e.ctrlKey && sides[e.key]) {
      e.preventDefault();
      this.moveToNeighbour(p, g, sides[e.key] as Side);
    } else if (e.shiftKey && sides[e.key]) {
      e.preventDefault();
      this.splitPane(p, sides[e.key]);
    } else if (!e.shiftKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
      e.preventDefault();
      const i = g.panes.indexOf(p) + (e.key === 'ArrowLeft' ? -1 : 2);
      this.set(addTab(this.ws, g.id, [p], Math.max(0, Math.min(g.panes.length, i)), p));
      this.root.querySelector<HTMLElement>(`[data-tab="${p}"] .name`)?.focus();
    }
  }

  /** Puts the tab into the group next to its own on `side`. */
  private moveToNeighbour(p: string, g: Group, side: Side) {
    if (locate(this.ws, p)?.kind !== 'tree') return;
    const boxes = layout(this.ws.tree).groups.map((q) => ({
      id: q.g.id,
      x: q.x,
      y: q.y,
      w: q.w,
      h: q.h,
    }));
    const to = neighbourGroup(boxes, g.id, side);
    if (!to) return this.say(`There is no group to the ${side}.`);
    this.set(addTab(removePane(this.ws, p), to, [p], null, p));
    this.root.querySelector<HTMLElement>(`[data-tab="${p}"] .name`)?.focus();
    this.say(`${titleOf(p)} moved to the group on the ${side}.`);
  }

  private showKeys() {
    const dialog = el('dialog', 'confirm');
    dialog.setAttribute('aria-labelledby', 'keys-title');
    const title = el('h2', undefined, 'Moving tabs with the keyboard');
    title.id = 'keys-title';
    const list = el('ul', 'confirm-list');
    for (const [keys, what] of TAB_KEYS) {
      const li = el('li');
      li.append(el('kbd', undefined, keys), el('span', 'muted', what));
      list.append(li);
    }
    const close = el('button', 'btn', 'Close');
    close.type = 'button';
    close.addEventListener('click', () => {
      dialog.close();
      dialog.remove();
    });
    dialog.append(title, list, close);
    document.body.append(dialog);
    dialog.showModal();
    // The key that chose the command is still down: on the Close button it would close this at once.
    dialog.tabIndex = -1;
    dialog.focus();
  }

  /** Says something to a screen reader. */
  private say(text: string) {
    this.announceEl.textContent = '';
    this.announceEl.textContent = text;
  }

  private onKey(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      this.openPalette();
    } else if (e.key === 'Escape' && this.palette) this.closePalette();
  }

  // ---- palette --------------------------------------------------------------------------------

  private commands(): Command[] {
    const c: Command[] = [];
    for (const p of PANES)
      c.push({
        label: `Open ${p.title}`,
        run: () => this.open(p.id),
        icon: paneIcon(p.id) ?? undefined,
      });
    for (const e of this.bench.listing())
      c.push({ label: `Go to ${e.name}`, run: () => this.select(e.id), icon: kindIcon(e.kinds) });
    const sel = this.selected;
    if (sel && this.bench.canUndo(sel))
      c.push({
        label: 'Undo the last change to this entry',
        run: () => this.bench.undo(sel),
        icon: 'undo',
      });
    const focus = this.focus;
    c.push({ label: `Float ${titleOf(focus)}`, run: () => this.floatPane(focus), icon: 'float' });
    for (const s of ['right', 'bottom', 'left', 'top'] as const)
      c.push({ label: `Split ${titleOf(focus)} to the ${s}`, run: () => this.splitPane(focus, s) });
    for (const f of this.ws.floats)
      c.push({
        label: `Dock window with ${titleOf(f.active)}`,
        run: () => this.dock(f.id),
        icon: 'dock',
      });
    c.push({ label: 'Keyboard shortcuts for tabs', run: () => this.showKeys() });
    c.push({ label: 'Reset layout', run: () => this.reset() });
    for (const p of PRESETS)
      c.push({
        label: `Layout: ${PRESET_LABEL[p]}`,
        run: () => this.layout(p),
        icon: LAYOUT_ICONS[p],
      });
    for (const [t, name] of THEMES)
      c.push({ label: `Theme: ${name}`, run: () => this.setTheme(t) });
    for (const [face, name] of FACES)
      c.push({ label: `Writing font: ${name}`, run: () => this.setSans(face === 'sans') });
    return c.concat(this.extra);
  }

  openPalette() {
    if (this.palette) return;
    const wrap = el('div', 'palette');
    const box = el('div', 'box');
    const input = el('input');
    input.type = 'text';
    input.placeholder = 'Type a command or an entry';
    input.setAttribute('aria-label', 'Command palette');
    const list = el('ul', 'results');
    box.append(input, list);
    wrap.append(box);
    wrap.addEventListener('pointerdown', (e) => {
      if (e.target === wrap) this.closePalette();
    });
    const all = this.commands();
    let sel = 0;
    let shown = all;
    const draw = () => {
      list.replaceChildren();
      shown.slice(0, 12).forEach((cmd, i) => {
        const li = el('li', i === sel ? 'on' : '');
        if (cmd.icon) li.append(icon(cmd.icon, 14));
        li.append(document.createTextNode(cmd.label));
        li.addEventListener('click', () => {
          this.closePalette();
          cmd.run();
        });
        list.append(li);
      });
    };
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      shown = all.filter((x) => x.label.toLowerCase().includes(q));
      sel = 0;
      draw();
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') sel = Math.min(Math.min(shown.length, 12) - 1, sel + 1);
      else if (e.key === 'ArrowUp') sel = Math.max(0, sel - 1);
      else if (e.key === 'Enter' && shown[sel]) {
        const cmd = shown[sel];
        this.closePalette();
        cmd.run();
        return;
      } else return;
      e.preventDefault();
      draw();
    });
    this.palette = wrap;
    document.body.append(wrap);
    draw();
    input.focus();
  }

  closePalette() {
    this.palette?.remove();
    this.palette = null;
  }
}

/** Remove one pane from its group but keep the group (it will receive a split). */
function removePaneKeepGroup(ws: Workspace, gid: string, pane: string): Workspace {
  const only = treeGroups(ws.tree).find((g) => g.id === gid);
  if (!only) return ws;
  const rest = only.panes.filter((p) => p !== pane);
  const fix = (g: Group): Group =>
    g.id === gid ? { ...g, panes: rest, active: rest.includes(g.active) ? g.active : rest[0] } : g;
  const walk = (n: Workspace['tree']): Workspace['tree'] =>
    !n
      ? n
      : n.t === 'g'
        ? fix(n)
        : { ...n, kids: n.kids.map((k) => walk(k) as NonNullable<Workspace['tree']>) };
  return { ...ws, tree: walk(ws.tree) };
}

/** The chords of a tab, as the shortcuts dialog lists them. */
const TAB_KEYS: [string, string][] = [
  ['← →  Home  End', 'Go to another tab of the group'],
  ['Alt + ← →', 'Move the tab among its group'],
  ['Alt + Shift + arrows', 'Split the tab out to that side'],
  ['Ctrl + Alt + arrows', 'Move the tab into the group on that side'],
  ['Alt + F', 'Float the tab in its own window'],
  ['Alt + D', 'Dock a floating tab back'],
];

/** What can be scrolled, and what names it from one drawing to the next. */
const SCROLLERS = '.grp > .body, .explorer .list, .grid-scroll';
const scrollKey = (e: HTMLElement): string =>
  `${e.closest('.grp')?.getAttribute('data-grp') ?? ''}|${e.className}`;
