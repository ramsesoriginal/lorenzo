// The outline of the work a page belongs to, as a tree beside the page (ADR 0494, W4): the
// Edition or Chapter at the top, its Chapters under it, each opened on demand, with its number
// and a mark on the page you are on. Pinned open from 1100px, a panel below it.
import { outlineOf, writingAddress } from './composition';
import { numberedTitle, numberingOf } from './numbering';

type Entry = Awaited<ReturnType<typeof outlineOf>>;

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, text = '', className = '') => {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
};

/** The entry at the top of the work `id` is part of, and the way down to `id`. */
export async function pathToTop(tenant: string, id: string): Promise<Entry[]> {
  const chain: Entry[] = [];
  let next: string | null | undefined = id;
  for (let depth = 0; next && depth < 24; depth++) {
    const entry: Entry = await outlineOf(tenant, next);
    chain.unshift(entry);
    next = entry.parent_id;
  }
  return chain;
}

export const hasOutline = (entry: Entry) =>
  ['edition', 'chapter'].includes(entry.kind) && !entry.joined && !entry.uses_scene_manuscript;

export async function outlineTree(tenant: string, current: string): Promise<HTMLElement | null> {
  const chain = await pathToTop(tenant, current);
  const top = chain[0];
  if (!top || !hasOutline(top)) return null;
  const labels = (await numberingOf(tenant, top.id).catch(() => null))?.labels ?? {};
  const open = new Set(chain.map((entry) => entry.id));

  const nav = el('nav', '', 'outline-tree');
  nav.setAttribute('aria-label', 'Outline');
  const list = el('ul');
  list.setAttribute('role', 'tree');
  nav.append(list);

  const row = (entry: { id: string; name: string }, level: number, expandable: boolean) => {
    const item = el('li');
    item.setAttribute('role', 'treeitem');
    item.setAttribute('aria-level', String(level));
    const line = el('div', '', 'row');
    const link = el('a', numberedTitle(entry.name, labels[entry.id]));
    link.href = writingAddress(tenant, entry.id);
    link.setAttribute('aria-label', `Go to ${numberedTitle(entry.name, labels[entry.id])}`);
    if (entry.id === current) link.setAttribute('aria-current', 'page');
    const children = el('ul');
    children.setAttribute('role', 'group');
    children.hidden = true;
    let loaded = false;
    const fill = async () => {
      if (loaded) return;
      loaded = true;
      const loadedEntry = await outlineOf(tenant, entry.id);
      const kids = loadedEntry.elements.filter((e) => e.kind === 'chapter');
      for (const kid of kids)
        children.append(row({ id: kid.id, name: kid.name ?? 'Chapter' }, level + 1, true));
      if (!kids.length) toggle.hidden = true;
    };
    const toggle = el('button', '▸', 'btn btn-secondary');
    toggle.type = 'button';
    toggle.setAttribute('aria-label', `Open ${entry.name}`);
    const show = async (visible: boolean) => {
      if (visible) await fill();
      children.hidden = !visible;
      item.setAttribute('aria-expanded', String(visible));
      toggle.textContent = visible ? '▾' : '▸';
      toggle.setAttribute('aria-label', `${visible ? 'Close' : 'Open'} ${entry.name}`);
    };
    toggle.addEventListener('click', () => void show(Boolean(children.hidden)));
    if (expandable) {
      line.append(toggle);
      item.setAttribute('aria-expanded', 'false');
    }
    line.append(link);
    item.append(line, children);
    if (expandable && open.has(entry.id) && entry.id !== current) void show(true);
    if (expandable && entry.id === current) void show(true);
    return item;
  };

  list.append(row({ id: top.id, name: top.name }, 1, true));
  return nav;
}
