import { pageState } from '@lorenzo/app-shell';
import { client, fetchAllPages, unwrap } from './api';
import { BRANDING_CSS_URL } from './config';
import {
  claim,
  el,
  empty,
  errorNotice,
  icon,
  link,
  loading,
  pageHead,
  relationshipHref,
  sectionHead,
} from './dom';
import { canManage, libraryName } from './names';
import { start } from './sign-in';

interface Doubled {
  ends: string;
  rows: { id: string; name: string }[];
}

/** The relationships the library has twice over: the same two ends (either way round for a two-way one). */
async function doubled(tenant: string): Promise<Doubled[]> {
  const rows = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/relationships', {
        params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
        cache: 'no-cache',
      }),
    ),
  );
  const groups = new Map<string, Doubled>();
  for (const r of rows) {
    const pair = r.one_way
      ? `${r.end_a.id}>${r.end_b.id}`
      : [r.end_a.id, r.end_b.id].sort().join('=');
    const group = groups.get(pair) ?? {
      ends: `${r.end_a.name} and ${r.end_b.name}`,
      rows: [],
    };
    group.rows.push({ id: r.id, name: r.name });
    groups.set(pair, group);
  }
  return [...groups.values()].filter((g) => g.rows.length > 1);
}

/** What looks wrong in what the reader may see, for those who manage relationships (ADR 0402). */
export async function mountProblems() {
  const host = document.querySelector<HTMLElement>('#social-problems');
  if (!host || !claim(host)) return;
  const tenant = new URLSearchParams(location.search).get('tenant');
  if (!tenant) {
    location.replace('/');
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Looking for problems…'));
    const [name, manage] = await Promise.all([libraryName(tenant), canManage(tenant)]);
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Problems', {
        lede: name
          ? `What looks wrong in the relationships of ${name}, as you may see them.`
          : 'What looks wrong in the relationships you may see.',
      }),
    );
    if (!manage) {
      view.append(empty('Problems are for the people who manage relationships in this library.'));
      host.replaceChildren(view);
      return;
    }
    const [read, twice] = await Promise.all([
      client.GET('/tenants/{tenant_id}/relationship-problems', {
        params: { path: { tenant_id: tenant } },
        cache: 'no-cache',
      }),
      doubled(tenant),
    ]);
    const chains = (await unwrap(read)).items;

    if (chains.length === 0 && twice.length === 0) {
      const none = el('div');
      none.append(
        pageState(BRANDING_CSS_URL, {
          art: 'caught-up',
          level: 2,
          title: 'No problems found',
          text: 'Nothing in what you can see looks wrong.',
        }),
      );
      view.append(none);
      host.replaceChildren(view);
      return;
    }

    if (chains.length) {
      const section = el('section', '', 'stack');
      section.append(sectionHead('Chains whose ends do not meet', { count: chains.length }));
      const list = el('ul', '', 'list');
      list.setAttribute('aria-label', 'Chains whose ends do not meet');
      for (const item of chains) {
        const row = el('li');
        const text = el('div', '', 'stack-tight grow');
        const title = el('div', '', 'row-tight');
        title.append(
          icon('warning'),
          link(item.relationship.name, relationshipHref(tenant, item.relationship.id)),
        );
        text.append(title, el('span', item.detail, 'status-text'));
        row.append(text);
        list.append(row);
      }
      section.append(list);
      view.append(section);
    }

    if (twice.length) {
      const section = el('section', '', 'stack');
      section.append(sectionHead('Doubled relationships', { count: twice.length }));
      const list = el('ul', '', 'list');
      list.setAttribute('aria-label', 'Doubled relationships');
      for (const group of twice) {
        const row = el('li');
        const text = el('div', '', 'stack-tight grow');
        text.append(el('span', `${group.rows.length} between ${group.ends}`));
        const names = el('div', '', 'row-tight');
        for (const r of group.rows) names.append(link(r.name, relationshipHref(tenant, r.id)));
        text.append(names);
        row.append(text);
        list.append(row);
      }
      section.append(list);
      view.append(section);
    }
    host.replaceChildren(view);
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}
