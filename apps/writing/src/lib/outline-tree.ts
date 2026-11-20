// The outline of the work a page belongs to, as a tree beside the page (ADR 0494, W4): the
// Edition or Chapter at the top, its Chapters under it, each opened on demand, with its number
// and a mark on the page you are on. Pinned open from 1100px, a panel below it.

import { confirmDialog } from '@lorenzo/app-shell';
import { client, unwrap } from './api';
import { CHAPTER_DRAG, entityOf, outlineOf, writingAddress } from './composition';
import { countSources } from './manuscript-count';
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

  const counts: (() => Promise<void>)[] = [];
  let running = false;
  const schedule = () => {
    if (running) return;
    running = true;
    setTimeout(async () => {
      while (counts.length) await (counts.shift() as () => Promise<void>)();
      running = false;
    }, 2000);
  };
  const nav = el('nav', '', 'outline-tree');
  nav.setAttribute('aria-label', 'Outline');
  const dropStatus = el('p', '', 'caption');
  dropStatus.setAttribute('role', 'status');
  nav.append(dropStatus);
  /** Move the Chapter `dragged` (from the page `from`) into `target`, before `before` or at the end. */
  const nest = async (from: string, dragged: string, target: string, before: string | null) => {
    const [child, source, destination] = await Promise.all([
      outlineOf(tenant, dragged),
      outlineOf(tenant, from),
      outlineOf(tenant, target),
    ]);
    dropStatus.textContent = `Moving ${child.name} into ${destination.name}`;
    await unwrap(
      await client.POST('/tenants/{tenant_id}/writing/entries/{id}/moves/{operation_id}', {
        params: {
          path: { tenant_id: tenant, id: dragged, operation_id: crypto.randomUUID() },
          header: { 'if-match': child.version },
        },
        body: {
          source_parent_id: source.id,
          destination_parent_id: destination.id,
          source_version: source.version,
          destination_version: destination.version,
          before_element_id: before,
        },
      }),
    );
    location.reload();
  };
  /** Put `dragged` before or after `anchor` among the parts of the page `from`. */
  const reorder = async (from: string, dragged: string, anchor: string, after: boolean) => {
    const page = await outlineOf(tenant, from);
    const ids = page.elements.map((x) => x.id).filter((x) => x !== dragged);
    ids.splice(ids.indexOf(anchor) + (after ? 1 : 0), 0, dragged);
    await unwrap(
      await client.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
        params: { path: { tenant_id: tenant, id: from }, header: { 'if-match': page.version } },
        body: { elements: ids },
      }),
    );
    location.reload();
  };
  /**
   * Join `dragged` into `destination` (Alt while dropping): into the Chapter just before it, or into
   * the parent whose row it is dropped on. Asks first, since the Chapter heading goes away.
   */
  const joinInto = async (
    from: string,
    dragged: string,
    destination: string,
    destinationParent: string | null,
  ) => {
    const [child, source, target] = await Promise.all([
      outlineOf(tenant, dragged),
      outlineOf(tenant, from),
      outlineOf(tenant, destination),
    ]);
    const parentMode = destination === from;
    if (!parentMode && destinationParent !== from) {
      dropStatus.textContent = 'Join a Chapter into its parent or into the Chapter before it.';
      return;
    }
    if (!parentMode) {
      const order = source.elements.map((x) => x.id);
      if (order[order.indexOf(dragged) - 1] !== destination) {
        dropStatus.textContent = 'Join a Chapter with the Chapter immediately before it.';
        return;
      }
    }
    if (
      !(await confirmDialog({
        title: `Join “${child.name}” into “${target.name}”?`,
        body: 'Its writing will take its place there, without its Chapter heading. Its name and notes remain at the old address.',
        confirm: 'Join chapters',
      }))
    )
      return;
    await unwrap(
      await client.POST('/tenants/{tenant_id}/writing/entries/{id}/joins/{operation_id}', {
        params: {
          path: { tenant_id: tenant, id: dragged, operation_id: crypto.randomUUID() },
          header: { 'if-match': child.version },
        },
        body: {
          mode: parentMode ? 'parent' : 'previous',
          destination_id: destination,
          parent_id: from,
          destination_version: target.version,
          parent_version: source.version,
        },
      }),
    );
    location.reload();
  };
  const list = el('ul');
  list.setAttribute('role', 'tree');
  nav.append(list);

  const row = (
    entry: { id: string; name: string },
    level: number,
    expandable: boolean,
    place?: { parent: string; next: string | null },
    droppable = expandable,
  ) => {
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
      for (const [at, kid] of kids.entries())
        children.append(
          row({ id: kid.id, name: kid.name ?? 'Chapter' }, level + 1, true, {
            parent: entry.id,
            next: kids[at + 1]?.id ?? null,
          }),
        );
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
    // A Chapter dragged from the page is dropped on a Chapter or Edition of the tree: on the middle
    // of its row to nest it there, on the top or bottom edge of a Chapter to put it before or after.
    if (droppable) {
      const zone = (event: DragEvent) => {
        const box = line.getBoundingClientRect();
        const at = (event.clientY - box.top) / Math.max(box.height, 1);
        return place && at < 0.25 ? 'before' : place && at > 0.75 ? 'after' : 'into';
      };
      line.addEventListener('dragover', (event) => {
        if (!event.dataTransfer?.types.includes(CHAPTER_DRAG)) return;
        event.preventDefault();
        line.dataset.drop = zone(event);
      });
      line.addEventListener('dragleave', () => {
        delete line.dataset.drop;
      });
      line.addEventListener('drop', (event) => {
        const where = zone(event);
        delete line.dataset.drop;
        const [from, dragged] = (event.dataTransfer?.getData(CHAPTER_DRAG) ?? '').split('|');
        if (!from || !dragged) return;
        event.preventDefault();
        const target = where === 'into' || !place ? entry.id : place.parent;
        const before =
          where === 'before' ? entry.id : where === 'after' ? (place?.next ?? null) : null;
        if (dragged === entry.id) return;
        if (from === target && where !== 'into') {
          // Within the same parent it is a reorder, written as the page writes it.
          void reorder(from, dragged, entry.id, where === 'after').catch((error: unknown) => {
            dropStatus.textContent =
              error instanceof Error ? error.message : 'This move could not be completed.';
          });
          return;
        }
        if (from === target) {
          dropStatus.textContent = 'It is already there.';
          return;
        }
        if (event.altKey) {
          void joinInto(from, dragged, entry.id, place?.parent ?? null).catch((error: unknown) => {
            dropStatus.textContent =
              error instanceof Error ? error.message : 'These Chapters could not be joined.';
          });
          return;
        }
        void nest(from, dragged, target, before).catch((error: unknown) => {
          dropStatus.textContent =
            error instanceof Error ? error.message : 'This move could not be completed.';
        });
      });
    }
    // The words of this entry's own text, found a little after the page has settled and one row
    // at a time, so the outline never competes with the page for the server (the API has no count).
    const words = el('span', '', 'caption');
    line.append(words);
    counts.push(async () => {
      try {
        const own = await entityOf(tenant, entry.id);
        const texts = own.information
          .filter((i) => i.type === 'manuscript')
          .flatMap((i) => i.payloads)
          .flatMap((p) => (p.kind === 'description' ? [p.content] : []));
        const n = countSources(texts);
        words.textContent = `${n} ${n === 1 ? 'word' : 'words'}`;
      } catch {
        // A count is a convenience.
      }
    });
    schedule();
    item.append(line, children);
    if (expandable && open.has(entry.id) && entry.id !== current) void show(true);
    if (expandable && entry.id === current) void show(true);
    return item;
  };

  list.append(row({ id: top.id, name: top.name }, 1, true));
  // The other Editions of the same Book are drop targets too, so a Chapter can be moved between them.
  if (top.kind === 'edition' && top.book_id) {
    const book = await outlineOf(tenant, top.book_id).catch(() => null);
    const others = (book?.editions ?? []).filter((edition) => edition.id !== top.id);
    if (others.length) {
      const group = el('ul');
      group.setAttribute('role', 'group');
      group.setAttribute('aria-label', 'Other Editions');
      for (const edition of others)
        group.append(row({ id: edition.id, name: edition.name }, 1, false, undefined, true));
      const label = el('p', 'Other Editions', 'caption');
      nav.append(label, group);
    }
  }
  return nav;
}
