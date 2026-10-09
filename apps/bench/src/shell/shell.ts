// The workbench shell: draws a Workspace (workspace/model.ts) and turns pointer and keyboard
// input into changes to it. The layout rules live in the model; this file is the DOM.

import type { Bench } from '../core/bench';
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
import { kindsText, redraw, renderEntry, renderLinks, statusText } from './entryPane';
import { PANE_IDS, PANES } from './stub';

const BAR = 30;
const STORE = 'bench:workspace';
const THEME = 'bench:theme';

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
  /** Commands the page adds to the palette, such as switching repository. */
  extra: { label: string; run: () => void }[] = [];

  private unsubscribe: (() => void) | null = null;

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
    this.applyTheme(this.theme());
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () =>
      this.applyTheme(this.theme()),
    );
    root.append(this.surface, this.overlay, this.ghost, this.mark);
    this.overlay.hidden = this.ghost.hidden = this.mark.hidden = true;
    window.addEventListener('pointermove', (e) => this.onMove(e));
    window.addEventListener('pointerup', (e) => this.onUp(e));
    window.addEventListener('keydown', (e) => this.onKey(e));
    this.unsubscribe = bench.subscribe(() => this.render());
    this.render();
  }

  /** Hands the shell the bench to show, once the session has said which repository it is. */
  use(bench: Bench) {
    this.unsubscribe?.();
    this.bench = bench;
    this.selected = null;
    this.unsubscribe = bench.subscribe(() => this.render());
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

  private theme(): string {
    try {
      return localStorage.getItem(THEME) ?? 'system';
    } catch {
      return 'system';
    }
  }
  private applyTheme(t: string) {
    const dark =
      t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }
  setTheme(t: string) {
    try {
      localStorage.setItem(THEME, t);
    } catch {
      /* ignore */
    }
    this.applyTheme(t);
  }

  select(id: string) {
    this.selected = id;
    void this.bench.open(id);
    this.set(showPane(this.ws, 'entry'));
  }

  open(pane: string) {
    this.focus = pane;
    this.set(showPane(this.ws, pane));
  }

  reset() {
    this.home = {};
    this.set(defaultWorkspace());
  }

  // ---- drawing --------------------------------------------------------------------------------

  private render() {
    const s = this.surface;
    // Keep what a person is typing when something else changes the page.
    const active = document.activeElement;
    const kept =
      active instanceof HTMLInputElement && active.dataset.key && s.contains(active)
        ? { key: active.dataset.key, value: active.value, at: active.selectionStart }
        : null;
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
    if (kept) {
      const input = s.querySelector<HTMLInputElement>(`input[data-key="${kept.key}"]`);
      if (input) {
        input.value = kept.value;
        input.focus();
        if (kept.at !== null) input.setSelectionRange(kept.at, kept.at);
      }
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
    if (floating) {
      const dock = el('button', 'icon', 'Dock');
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
    const b = el('button', 'name', titleOf(p));
    b.type = 'button';
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(p === g.active));
    b.addEventListener('click', () => {
      this.focus = p;
      this.set(setActive(this.ws, g.id, p));
    });
    b.addEventListener('keydown', (e) => this.onTabKey(e, g, p));
    const x = el('button', 'x', '×');
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

  private paneEl(id: string): HTMLElement {
    const bench = this.bench;
    if (id === 'entry') return renderEntry(bench, this.selected, (x) => this.select(x));
    if (id === 'links') return renderLinks(bench, this.selected, (x) => this.select(x));
    const c = el('div', `pane pane-${id}`);
    if (id === 'explorer') {
      if (bench.loadError && !bench.entries.length) c.append(el('p', 'bad', bench.loadError));
      c.append(this.newEntryForm());
      const list = el('ul', 'list');
      for (const e of bench.listing()) {
        const li = el('li');
        const b = el('button', e.id === this.selected ? 'row on' : 'row', e.name);
        b.type = 'button';
        b.dataset.entry = e.id;
        b.title = bench.status(e.id) === 'synced' ? kindsText(e.kinds) : statusText(bench, e.id);
        b.addEventListener('click', () => this.select(e.id));
        li.append(b);
        list.append(li);
      }
      c.append(list);
    } else if (id === 'props') {
      c.append(el('p', 'muted', 'Stats are not editable yet.'));
    }
    return c;
  }

  /** Name, kind and parent of an entry to make; it shows in the list at once. */
  private newEntryForm(): HTMLElement {
    const bench = this.bench;
    const form = el('form', 'new-entry');
    const name = el('input');
    name.type = 'text';
    name.placeholder = 'New entry';
    name.dataset.key = 'new-entry-name';
    name.setAttribute('aria-label', 'Name of the new entry');
    const kind = el('select');
    kind.setAttribute('aria-label', 'Kind of the new entry');
    for (const [value, label] of [
      ['item', 'Item'],
      ['being', 'Being'],
      ['item,being', 'Item and being'],
      ['', 'Bare entry'],
    ] as const)
      kind.append(new Option(label, value));
    const parent = el('select');
    parent.setAttribute('aria-label', 'Parent of the new entry');
    parent.append(new Option('No parent', ''));
    for (const e of bench.listing())
      parent.append(new Option(e.name, e.id, false, e.id === this.selected));
    const add = el('button', 'btn', 'Add');
    add.type = 'submit';
    form.append(name, kind, parent, add);
    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const text = name.value.trim();
      if (!text) return;
      const id = bench.create({
        name: text,
        kinds: kind.value ? kind.value.split(',') : [],
        parents: parent.value ? [parent.value] : [],
      });
      name.value = '';
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
    this.floatTab([pane], pane, Math.max(8, this.rect().width - 460 - n * 28), 48 + n * 28);
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
    if (!e.altKey) return;
    const sides: Record<string, Side> = {
      ArrowLeft: 'left',
      ArrowRight: 'right',
      ArrowUp: 'top',
      ArrowDown: 'bottom',
    };
    if (e.key === 'f' || e.key === 'F') {
      e.preventDefault();
      this.floatPane(p);
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

  private onKey(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      this.openPalette();
    } else if (e.key === 'Escape' && this.palette) this.closePalette();
  }

  // ---- palette --------------------------------------------------------------------------------

  private commands(): { label: string; run: () => void }[] {
    const c: { label: string; run: () => void }[] = [];
    for (const p of PANES) c.push({ label: `Open ${p.title}`, run: () => this.open(p.id) });
    for (const e of this.bench.listing())
      c.push({ label: `Go to ${e.name}`, run: () => this.select(e.id) });
    const sel = this.selected;
    if (sel && this.bench.canUndo(sel))
      c.push({ label: 'Undo the last change to this entry', run: () => this.bench.undo(sel) });
    const focus = this.focus;
    c.push({ label: `Float ${titleOf(focus)}`, run: () => this.floatPane(focus) });
    for (const s of ['right', 'bottom', 'left', 'top'] as const)
      c.push({ label: `Split ${titleOf(focus)} to the ${s}`, run: () => this.splitPane(focus, s) });
    for (const f of this.ws.floats)
      c.push({ label: `Dock window with ${titleOf(f.active)}`, run: () => this.dock(f.id) });
    c.push({ label: 'Reset layout', run: () => this.reset() });
    for (const t of ['system', 'light', 'dark'])
      c.push({ label: `Appearance: ${t}`, run: () => this.setTheme(t) });
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
        const li = el('li', i === sel ? 'on' : '', cmd.label);
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
