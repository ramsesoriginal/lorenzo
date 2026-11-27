import { openMenu, pageState } from '@lorenzo/app-shell';
import { createGraphView, type LayoutName, LIMITS } from '@lorenzo/graph-renderer';
import { BRANDING_CSS_URL } from './config';
import { formDialog } from './dialog';
import {
  audienceBadge,
  button,
  claim,
  el,
  empty,
  errorNotice,
  field,
  icon,
  link,
  loading,
  message,
  pageHead,
  select,
} from './dom';
import { canManage, libraryName, myLibraries } from './names';
import { shellOf, start } from './sign-in';
import { createWeb, deleteWeb, type Layout, listWebs, readGraph, renameWeb } from './web-api';
import { audienceWords } from './words';

const LAYOUTS: Layout[] = ['circle', 'radial', 'stress', 'forceatlas2', 'manual', 'layered'];
const LAYOUT_WORDS: Record<Layout, string> = {
  circle: 'Circle',
  radial: 'Radial',
  stress: 'Stress',
  forceatlas2: 'Force-directed',
  manual: 'Placed by hand',
  layered: 'Layered',
};

const lastKey = (tenant: string) => `lorenzo:social:last-web:${tenant}`;
const lastLibrary = 'lorenzo:social:last-library';

/** The web a person opened last in a library, so Home can offer to continue it. */
export function rememberWeb(tenant: string, id: string) {
  try {
    localStorage.setItem(lastKey(tenant), id);
    localStorage.setItem(lastLibrary, tenant);
  } catch {
    // Without storage there is nothing to continue; nothing else changes.
  }
}

const recalled = (key: string) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

const webHref = (tenant: string, id: string) => `/web/?${new URLSearchParams({ tenant, id })}`;

/** Home is the webs of the library the person works in; the shell's switcher changes library. */
export async function mountHome() {
  const host = document.querySelector<HTMLElement>('#social-home');
  if (!host || !claim(host)) return;
  const params = new URLSearchParams(location.search);
  const named = params.get('tenant');
  if (named) {
    location.replace(`/webs/?${new URLSearchParams({ tenant: named })}`);
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening your libraries…'));
    const libraries = await myLibraries();
    const chosen =
      libraries.find((library) => library.id === recalled(lastLibrary)) ??
      (libraries.length === 1 ? libraries[0] : undefined);
    if (chosen) {
      location.replace(`/webs/?${new URLSearchParams({ tenant: chosen.id })}`);
      return;
    }
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Social', {
        lede: 'Who knows whom: the relationships of your libraries, and how much each one counts.',
      }),
    );
    if (libraries.length) {
      const list = el('ul', '', 'list');
      list.setAttribute('aria-label', 'Libraries');
      for (const library of libraries) {
        const row = el('li');
        const text = el('div', '', 'stack-tight grow');
        text.append(link(library.name, `/webs/?${new URLSearchParams({ tenant: library.id })}`));
        row.append(text, el('span', library.role, 'chip'));
        list.append(row);
      }
      view.append(list);
    } else {
      view.append(empty('You are not in a library yet.'));
    }
    host.replaceChildren(view);
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}

/** The webs of one library: Continue, the list, and for writers a new web, rename and delete. */
export async function mountWebs() {
  const host = document.querySelector<HTMLElement>('#social-webs');
  if (!host || !claim(host)) return;
  const tenant = new URLSearchParams(location.search).get('tenant');
  if (!tenant) {
    location.replace('/');
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  const shell = shellOf();
  try {
    host.replaceChildren(loading('Opening the webs…'));
    const [name, manage] = await Promise.all([libraryName(tenant), canManage(tenant)]);
    try {
      localStorage.setItem(lastLibrary, tenant);
    } catch {
      // A library that cannot be remembered is chosen again next time.
    }

    const draw = async () => {
      const first = await listWebs(tenant, 1);
      const view = el('div', '', 'stack view');
      const newWeb = manage
        ? button('New web', () => makeOne(), { variant: 'primary', icon: 'add' })
        : null;
      view.append(
        pageHead('Webs', {
          lede: name
            ? `The saved views of the relationships of ${name}.`
            : 'Saved views of relationships.',
          actions: newWeb ? [newWeb] : [],
        }),
      );

      // A web as a card: its drawing, its name and what it holds, and a menu for those who may change it.
      const cardOf = (web: (typeof first.items)[number], heading: 'h2' | 'h3') => {
        const item = el('li', '', 'web-card');
        const thumb = el('div', '', 'web-thumb');
        thumb.setAttribute('aria-hidden', 'true');
        thumb.inert = true;
        const head = el('div', '', 'row-tight');
        const title = el(heading, '', 'web-card-title grow');
        title.append(link(web.name, webHref(tenant, web.id)));
        head.append(title);
        if (manage) {
          const more = el('button', '', 'icon-button');
          more.type = 'button';
          more.setAttribute('aria-label', `More about ${web.name}`);
          more.append(icon('more'));
          more.addEventListener('click', () => {
            openMenu(
              more,
              [
                { label: 'Rename…', icon: 'edit', run: () => void renameOne(web.id, web.name) },
                { separator: true },
                {
                  label: 'Delete…',
                  icon: 'delete',
                  danger: true,
                  run: () => void deleteOne(web.id, web.name),
                },
              ],
              { label: web.name, sprite: `${BRANDING_CSS_URL}/icons.svg` },
            );
          });
          head.append(more);
        }
        const counts = el('span', '', 'status-text');
        const foot = el('div', '', 'row-tight');
        foot.append(counts);
        if (web.is_public !== null && web.is_public !== undefined) {
          foot.append(audienceBadge(audienceWords(web.is_public), web.is_public));
        }
        item.append(thumb, head, foot);
        // The drawing and the counts are read when the card comes into view.
        const fill = () => void drawThumbnail(tenant, web, thumb, counts);
        if ('IntersectionObserver' in window) {
          const watch = new IntersectionObserver((seen) => {
            if (seen.some((x) => x.isIntersecting)) {
              watch.disconnect();
              fill();
            }
          });
          watch.observe(item);
        } else fill();
        return item;
      };

      const remembered = first.items.find((web) => web.id === recalled(lastKey(tenant)));
      if (remembered) {
        const block = el('section', '', 'stack-tight');
        block.setAttribute('aria-label', 'Continue');
        const strip = el('ul', '', 'web-cards');
        strip.append(cardOf(remembered, 'h3'));
        block.append(el('h2', 'Continue', 'group-title'), strip);
        view.append(block);
      }

      if (first.items.length === 0) {
        const none = el('div');
        none.append(
          pageState(BRANDING_CSS_URL, {
            art: 'empty-social-web',
            alt: 'Illustration: empty-social-web. No webs yet',
            level: 2,
            title: 'There are no webs you can see yet.',
            text: manage
              ? 'A web is a saved view of who is tied to whom. Make one to start.'
              : 'A web is a saved view of who is tied to whom. A Game Master or an Author makes them.',
            actions: manage ? [{ label: 'New web', primary: true, run: () => void makeOne() }] : [],
          }),
        );
        view.append(none);
        host.replaceChildren(view);
        return;
      }

      const list = el('ul', '', 'web-cards');
      list.setAttribute('aria-label', 'Webs');
      for (const web of first.items) list.append(cardOf(web, 'h3'));
      view.append(el('h2', 'All webs', 'group-title'), list);
      host.replaceChildren(view);
    };

    const makeOne = async () => {
      const named = field('Name');
      named.input.required = true;
      const layouts = select(
        'Layout',
        LAYOUTS.map((layout) => [layout, LAYOUT_WORDS[layout]]),
        'circle',
      );
      const visible = field('Everyone in the library may see it', '', 'checkbox');
      await formDialog({
        title: 'Make a web',
        submit: 'Make the web',
        fields: [named.label, layouts.label, visible.label],
        async run() {
          const made = await createWeb(tenant, {
            name: named.input.value.trim(),
            layout: layouts.input.value as Layout,
            is_public: visible.input.checked,
          });
          location.assign(webHref(tenant, made.id));
        },
      });
    };

    const renameOne = async (id: string, current: string) => {
      const named = field('Name', current);
      named.input.required = true;
      await formDialog({
        title: 'Rename the web',
        submit: 'Rename',
        fields: [named.label],
        async run() {
          await renameWeb(tenant, id, named.input.value.trim());
          await draw();
          shell?.toast({ kind: 'ok', title: 'Renamed' });
        },
      });
    };

    const deleteOne = async (id: string, current: string) => {
      const yes = await shell?.confirm({
        title: `Delete ${current}?`,
        body: [
          'The web goes, with which entries it shows and how it is drawn.',
          'The entries and their relationships stay as they are.',
        ],
        confirm: 'Delete the web',
        danger: true,
      });
      if (!yes) return;
      try {
        await deleteWeb(tenant, id);
        await draw();
        shell?.toast({ kind: 'ok', title: 'Web deleted' });
      } catch (error) {
        shell?.toast({ kind: 'error', title: 'Could not delete the web', text: message(error) });
      }
    };

    await draw();
    // The palette's "New web…" lands here with the dialog open.
    if (manage && new URLSearchParams(location.search).get('new') === '1') void makeOne();
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}

/**
 * A web's small drawing and what it holds, for its card: the graph as the reader may see it, laid out
 * as the web is, with no labels. A web too big to draw gets its counts and no picture.
 */
async function drawThumbnail(
  tenant: string,
  web: { id: string; name: string; layout: string; layout_seed: number },
  thumb: HTMLElement,
  counts: HTMLElement,
) {
  try {
    const graph = await readGraph(tenant, web.id);
    const entries = graph.members.length;
    const ties = graph.edges.filter((e) => e.as_of !== 'not_yet' && e.as_of !== 'ended').length;
    counts.textContent = `${entries} ${entries === 1 ? 'entry' : 'entries'} · ${ties} ${ties === 1 ? 'relationship' : 'relationships'}`;
    if (entries === 0 || entries > LIMITS.nodes || ties > LIMITS.edges) return;
    const handle = createGraphView(thumb, {
      model: {
        nodes: graph.members.map((m) => ({ id: m.entry.id, name: m.entry.name })),
        edges: graph.edges
          .filter((e) => e.as_of !== 'not_yet' && e.as_of !== 'ended')
          .map((e) => ({
            id: e.id,
            a: e.end_a.id,
            b: e.end_b.id,
            directed: false,
            status: 'direct' as const,
          })),
      },
      title: web.name,
      view: {
        layout: web.layout as LayoutName,
        seed: web.layout_seed,
        labels: false,
        positions: Object.fromEntries(
          graph.members
            .filter((m) => m.x != null && m.y != null)
            .map((m) => [m.entry.id, { x: m.x as number, y: m.y as number }]),
        ),
      },
    });
    void handle;
  } catch {
    // A card without its drawing is still a card.
  }
}
