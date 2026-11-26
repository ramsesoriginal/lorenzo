import { pageState } from '@lorenzo/app-shell';
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
import { createWeb, deleteWeb, type Layout, listWebs, renameWeb } from './web-api';
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

      const remembered = first.items.find((web) => web.id === recalled(lastKey(tenant)));
      if (remembered) {
        const card = el('section', '', 'stack-tight');
        card.setAttribute('aria-label', 'Continue');
        const row = el('div', '', 'row-tight');
        row.append(
          icon('kind-social-web'),
          el('span', 'Continue where you left off: ', 'status-text'),
          link(remembered.name, webHref(tenant, remembered.id)),
        );
        card.append(row);
        view.append(card);
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

      const list = el('ul', '', 'list');
      list.setAttribute('aria-label', 'Webs');
      for (const web of first.items) {
        const row = el('li');
        const text = el('div', '', 'stack-tight grow');
        const title = el('div', '', 'row-tight');
        title.append(icon('kind-social-web'), link(web.name, webHref(tenant, web.id)));
        text.append(
          title,
          el(
            'span',
            `Laid out as ${LAYOUT_WORDS[web.layout as Layout] ?? web.layout}`,
            'status-text',
          ),
        );
        row.append(text);
        if (web.is_public !== null && web.is_public !== undefined) {
          row.append(audienceBadge(audienceWords(web.is_public), web.is_public));
        }
        if (manage) {
          const tools = el('div', '', 'row-tight');
          tools.append(
            button('Rename', () => renameOne(web.id, web.name), { variant: 'secondary' }),
            button('Delete', () => deleteOne(web.id, web.name), { variant: 'danger' }),
          );
          tools.querySelectorAll('button')[0]?.setAttribute('aria-label', `Rename ${web.name}`);
          tools.querySelectorAll('button')[1]?.setAttribute('aria-label', `Delete ${web.name}`);
          row.append(tools);
        }
        list.append(row);
      }
      view.append(list);
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
