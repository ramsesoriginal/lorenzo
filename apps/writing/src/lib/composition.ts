import { parse, render } from '@lorenzo/lorenzoscript';
import { client, LorenzoApiError, loadFile, unwrap } from './api';

const node = <K extends keyof HTMLElementTagNameMap>(tag: K, text = '') => {
  const el = document.createElement(tag);
  el.textContent = text;
  return el;
};
export const writingAddress = (tenant: string, entry: string, view = '') =>
  `/?${new URLSearchParams({ tenant, entry, ...(view ? { view } : {}) })}`;
const link = (title: string, href: string) => {
  const a = node('a', title);
  a.href = href;
  return a;
};
const button = (title: string, action: () => Promise<void>) => {
  const b = node('button', title);
  b.type = 'button';
  b.className = 'btn btn-secondary';
  b.addEventListener('click', () => {
    b.disabled = true;
    void action().finally(() => {
      b.disabled = false;
    });
  });
  return b;
};
export const outlineOf = async (tenant: string, id: string) =>
  unwrap(
    await client.GET('/tenants/{tenant_id}/writing/entries/{id}', {
      params: { path: { tenant_id: tenant, id } },
    }),
  );

export async function compositionScreen(
  host: HTMLElement,
  tenant: string,
  id: string,
  reading: boolean,
) {
  const current = await outlineOf(tenant, id);
  const actual = current.kind === 'book' ? current.editions[0]?.id : id;
  if (!actual) throw new Error('This Book has no Edition to open.');
  if (actual !== id) {
    location.replace(writingAddress(tenant, actual, reading ? 'read' : 'outline'));
    return;
  }
  const heading = node('h1', current.name);
  const nav = node('nav');
  nav.setAttribute('aria-label', 'Manuscript views');
  nav.className = 'row';
  nav.append(
    link('Write', writingAddress(tenant, id)),
    link(reading ? 'Outline' : 'Read', writingAddress(tenant, id, reading ? 'outline' : 'read')),
  );
  if (current.parent_id)
    nav.append(link('Up to parent', writingAddress(tenant, current.parent_id, 'outline')));
  const status = node('p');
  status.setAttribute('role', 'status');
  const report = (error: unknown) => {
    status.textContent = error instanceof Error ? error.message : 'This could not be completed.';
  };
  host.replaceChildren(heading, nav, status);
  if (reading) {
    const article = node('article');
    article.className = 'ls-content';
    host.append(article);
    // Iterative, depth-first assembly; every entry and bundle is authorized by the API.
    const tasks: (
      | { kind: 'entry'; id: string }
      | {
          kind: 'payload';
          payload: Awaited<ReturnType<typeof entityOf>>['information'][number]['payloads'][number];
        }
    )[] = [{ kind: 'entry', id }];
    while (tasks.length) {
      const task = tasks.pop();
      if (!task) continue;
      if (task.kind === 'entry') {
        try {
          const outline = await outlineOf(tenant, task.id);
          const entry = await entityOf(tenant, task.id);
          if (task.id !== id) article.append(node('h2', entry.name));
          const payloads = new Map(
            entry.information
              .filter((i) => i.type === 'manuscript')
              .flatMap((i) => i.payloads)
              .map((p) => [p.id, p]),
          );
          for (const item of [...outline.elements].reverse()) {
            if (item.kind === 'chapter') tasks.push({ kind: 'entry', id: item.id });
            else {
              const payload = payloads.get(item.id);
              if (payload) tasks.push({ kind: 'payload', payload });
            }
          }
        } catch (error) {
          if (error instanceof LorenzoApiError && error.status === 404) continue;
          throw error;
        }
      } else if (task.payload.kind === 'description') {
        const part = node('section');
        part.innerHTML = render(parse(task.payload.content), { externalImages: false });
        article.append(part);
      } else if (task.payload.kind === 'picture') {
        const img = node('img');
        img.alt = 'Manuscript illustration';
        img.src = await loadFile(task.payload);
        article.append(img);
      }
    }
    return;
  }
  const list = node('ol');
  host.append(list);
  const own = await entityOf(tenant, id);
  const payloads = new Map(
    own.information
      .filter((i) => i.type === 'manuscript')
      .flatMap((i) => i.payloads)
      .map((p) => [p.id, p]),
  );
  const saveOrder = async (ids: string[]) => {
    try {
      await unwrap(
        await client.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
          params: { path: { tenant_id: tenant, id }, header: { 'if-match': current.version } },
          body: { elements: ids },
        }),
      );
      await compositionScreen(host, tenant, id, false);
    } catch (error) {
      report(error);
    }
  };
  for (const [index, item] of current.elements.entries()) {
    const li = node('li');
    li.className = 'stack-tight';
    const p = payloads.get(item.id);
    const label =
      item.kind === 'chapter'
        ? (item.name ?? 'Chapter')
        : p?.kind === 'description'
          ? p.content.slice(0, 80) || 'Empty text'
          : 'Picture';
    li.append(
      item.kind === 'chapter' ? link(label, writingAddress(tenant, item.id)) : node('span', label),
    );
    const controls = node('div');
    controls.className = 'row';
    for (const [label, delta] of [
      ['Up', -1],
      ['Down', 1],
    ] as const) {
      const move = button(label, async () => {
        const ids = current.elements.map((x) => x.id);
        const target = index + delta;
        [ids[index], ids[target]] = [ids[target], ids[index]];
        await saveOrder(ids);
      });
      move.setAttribute('aria-label', `${label}: ${item.name ?? 'text or picture'}`);
      move.disabled = index + delta < 0 || index + delta >= current.elements.length;
      controls.append(move);
    }
    if (item.kind === 'chapter')
      controls.append(
        link('Subchapters', writingAddress(tenant, item.id, 'outline')),
        button('Remove from outline', async () =>
          saveOrder(current.elements.filter((x) => x.id !== item.id).map((x) => x.id)),
        ),
      );
    li.append(controls);
    list.append(li);
  }
  const name = node('input');
  name.className = 'text-input';
  name.placeholder = 'Chapter title';
  name.setAttribute('aria-label', 'New chapter title');
  name.maxLength = 300;
  const creationId = crypto.randomUUID();
  host.append(
    name,
    button('Add chapter', async () => {
      try {
        const made = await unwrap(
          await client.POST('/tenants/{tenant_id}/writing/chapters', {
            params: { path: { tenant_id: tenant } },
            body: { id: creationId, name: name.value.trim() || 'Untitled chapter' },
          }),
        );
        await saveOrder([...current.elements.map((x) => x.id), made.id]);
      } catch (error) {
        report(error);
      }
    }),
  );
  const existing = node('details');
  existing.append(node('summary', 'Place an existing Chapter'));
  host.append(existing);
  const search = node('input');
  search.type = 'search';
  search.className = 'text-input';
  search.setAttribute('aria-label', 'Find a Chapter');
  search.placeholder = 'Chapter title';
  const matches = node('div');
  matches.className = 'stack-tight';
  existing.append(
    search,
    button('Find Chapters', async () => {
      try {
        matches.replaceChildren();
        const chapters = await unwrap(
          await client.GET('/tenants/{tenant_id}/entities', {
            params: {
              path: { tenant_id: tenant },
              query: { page: 1, size: 10, kind: ['chapter'], q: search.value.trim() },
            },
          }),
        );
        for (const chapter of chapters.items) {
          if (chapter.id === id) continue;
          const outline = await outlineOf(tenant, chapter.id);
          if (!outline.parent_id)
            matches.append(
              button(chapter.name, async () =>
                saveOrder([...current.elements.map((x) => x.id), chapter.id]),
              ),
            );
        }
        if (!matches.children.length)
          matches.append(node('p', 'No unassigned Chapters found. Try another title.'));
        if (chapters.total > 10)
          matches.append(
            node('p', 'Showing the first ten matches. Refine the title to find more.'),
          );
      } catch (error) {
        report(error);
      }
    }),
    matches,
  );
  if (current.kind === 'edition') {
    const editions = node('details');
    editions.append(node('summary', 'Editions'));
    host.append(editions);
    for (const edition of current.editions)
      editions.append(
        link(edition.name, writingAddress(tenant, edition.id, 'outline')),
        node('br'),
      );
    const name = node('input');
    name.className = 'text-input';
    name.setAttribute('aria-label', 'New edition title');
    name.maxLength = 300;
    const copyId = crypto.randomUUID();
    editions.append(
      name,
      button('Create independent edition', async () => {
        try {
          const made = await unwrap(
            await client.POST('/tenants/{tenant_id}/writing/editions', {
              params: { path: { tenant_id: tenant } },
              body: { id: copyId, name: name.value.trim() || 'New edition', source_edition_id: id },
            }),
          );
          location.assign(writingAddress(tenant, made.id, 'outline'));
        } catch (error) {
          report(error);
        }
      }),
    );
  }
}
async function entityOf(tenant: string, id: string) {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenant, entity_id: id } },
    }),
  );
}
