// The shelf: Writing's Home (ADR 0494, W1). Start writing at the top, Continue, the work as a
// list with a filter and a search, and what has been shared with the person for review.
import { openMenu, regionState } from '@lorenzo/app-shell';
import { client, fetchAllPages, unwrap } from './api';
import { BRANDING_CSS_URL } from './config';
import { importDocuments, sortFiles } from './formats/import';
import { fromMarkdown } from './formats/markdown';
import {
  byRecent,
  editedWords,
  FILTERS,
  type Kind,
  lastWork,
  STARTS,
  shown,
  type Work,
} from './shelf-list';

const KIND_WORDS: Record<string, string> = {
  scene: 'Scene',
  scene_telling: 'Scene',
  book: 'Book',
  chapter: 'Chapter',
  carrier: 'Carrier',
  biography: 'Character biography',
};

function el<K extends keyof HTMLElementTagNameMap>(tag: K, text = '', className = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

const address = (tenant: string, entry?: string) =>
  `${entry ? '/write/' : '/'}?${new URLSearchParams({ tenant, ...(entry ? { entry } : {}) })}`;

const message = (error: unknown) =>
  error instanceof Error ? error.message : 'This could not be completed.';

export async function shelf(host: HTMLElement, tenant: string) {
  const heading = el('h1', 'Your writing');

  const title = el('input', '', 'text-input');
  title.placeholder = 'Untitled';
  title.maxLength = 300;
  title.setAttribute('aria-label', 'New draft title');

  const status = el('p', '', 'caption');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-label', 'Save status');

  let creationId = crypto.randomUUID();
  const firstEditionId = crypto.randomUUID();
  const controls: HTMLButtonElement[] = [];

  const start = (kind: Kind) => {
    for (const control of controls) control.disabled = true;
    void (async () => {
      try {
        const name = title.value.trim() || 'Untitled';
        if (kind === 'scene') {
          const scene = await unwrap(
            await client.POST('/tenants/{tenant_id}/scenes', {
              params: { path: { tenant_id: tenant } },
              body: { id: creationId, name, is_public: false },
            }),
          );
          location.assign(address(tenant, scene.id));
          return;
        }
        const route =
          kind === 'book'
            ? '/tenants/{tenant_id}/writing/books'
            : kind === 'carrier'
              ? '/tenants/{tenant_id}/writing/carriers'
              : kind === 'biography'
                ? '/tenants/{tenant_id}/writing/biographies'
                : '/tenants/{tenant_id}/writing/chapters';
        const made = await unwrap(
          await client.POST(route, {
            params: { path: { tenant_id: tenant } },
            body: { id: creationId, first_edition_id: firstEditionId, name },
          }),
        );
        location.assign(address(tenant, made.kind === 'book' ? made.editions[0]?.id : made.id));
      } catch (error) {
        status.textContent = message(error);
        creationId = crypto.randomUUID();
        for (const control of controls) control.disabled = false;
      }
    })();
  };

  const startWriting = el('button', 'Start writing', 'btn btn-primary');
  startWriting.type = 'button';
  startWriting.addEventListener('click', () => start('scene'));

  const more = el('button', 'Start something else', 'btn btn-secondary');
  more.type = 'button';
  more.setAttribute('aria-haspopup', 'menu');
  // Bring documents in (ADR 0521): Markdown files, or a whole folder of them from a vault.
  const picker = el('input');
  picker.type = 'file';
  picker.multiple = true;
  picker.hidden = true;
  picker.accept = '.md,.markdown,.txt,text/markdown,text/plain';
  picker.setAttribute('aria-label', 'Choose files to import');
  const pick = (folder: boolean) => {
    picker.value = '';
    picker.webkitdirectory = folder;
    picker.click();
  };
  picker.addEventListener('change', () => {
    const { readable, skipped } = sortFiles(Array.from(picker.files ?? []));
    if (readable.length === 0) {
      status.textContent = 'No Markdown files were found to import.';
      return;
    }
    for (const control of controls) control.disabled = true;
    status.textContent = `Importing ${readable.length} ${readable.length === 1 ? 'file' : 'files'}…`;
    void (async () => {
      try {
        const docs = await Promise.all(
          readable.map(async (file) => fromMarkdown(file.name, await file.text())),
        );
        const folder = readable[0]?.webkitRelativePath.split('/')[0];
        const done = await importDocuments(tenant, docs, folder || 'Imported writing');
        const link = el('a', done.chapters === 1 ? `Open “${done.name}”` : `Open “${done.name}”`);
        link.href = address(tenant, done.entry);
        status.replaceChildren(
          `Imported ${done.chapters} ${done.chapters === 1 ? 'Chapter' : 'Chapters'}${
            done.links ? `, with ${done.links} [[links]] to review` : ''
          }${skipped.length ? `; left out: ${skipped.join(', ')}` : ''}. `,
          link,
        );
      } catch (error) {
        status.textContent = message(error);
      } finally {
        for (const control of controls) control.disabled = false;
      }
    })();
  });
  more.addEventListener('click', () =>
    openMenu(
      more,
      [
        ...STARTS.map((s) => ({
          label: `${s.label}: ${s.line}`,
          run: () => start(s.kind),
        })),
        { label: 'Import Markdown files', run: () => pick(false) },
        { label: 'Import a folder of Markdown files', run: () => pick(true) },
      ],
      { label: 'Start something else', sprite: `${BRANDING_CSS_URL}/icons.svg` },
    ),
  );
  controls.push(startWriting, more);

  const row = el('div', '', 'row');
  row.append(title, startWriting, more, picker);

  const body = el('div', '', 'stack');
  host.replaceChildren(heading, row, status, body);
  body.append(regionState(`${BRANDING_CSS_URL}/icons.svg`, { kind: 'loading' }));

  const [entities, biographies, shared] = await Promise.all([
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/entities', {
          params: {
            path: { tenant_id: tenant },
            query: {
              page,
              size: 100,
              kind: ['scene', 'book', 'chapter', 'scene_telling', 'carrier'],
            },
          },
        }),
      ),
    ),
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/writing/biographies', {
          params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
        }),
      ),
    ),
    unwrap(await client.GET('/me/writing-reviews')).catch(() => []),
  ]);

  const works: Work[] = [
    ...entities.map((e) => ({
      id: e.id,
      name: e.name,
      kind: e.kinds[0] ?? 'scene',
      edited: e.updated_at,
    })),
    ...biographies.map((b) => ({ id: b.id, name: b.name, kind: 'biography' })),
  ];

  let filter = 'all';
  let query = '';

  const bar = el('div', '', 'row');
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', 'Show');
  const chips = FILTERS.map((f) => {
    const chip = el('button', f.label, 'btn btn-secondary');
    chip.type = 'button';
    chip.addEventListener('click', () => {
      filter = f.id;
      paint();
    });
    return { f, chip };
  });
  bar.append(...chips.map((c) => c.chip));

  const search = el('input', '', 'text-input');
  search.type = 'search';
  search.placeholder = 'Search your writing';
  search.setAttribute('aria-label', 'Search your writing');
  search.addEventListener('input', () => {
    query = search.value;
    paint();
  });

  const list = el('ul', '', 'list');
  const count = el('p', '', 'caption');
  count.setAttribute('role', 'status');
  count.setAttribute('aria-label', 'Works shown');
  const empty = el('div');

  const last = lastWork();
  const resume = last && last.tenant === tenant ? works.find((w) => w.id === last.entry) : null;
  const resumeLine = el('p');
  if (resume) {
    const link = el('a', `Continue with ${resume.name}`);
    link.href = address(tenant, resume.id);
    resumeLine.append(link);
  }

  function paint() {
    for (const { f, chip } of chips) chip.setAttribute('aria-pressed', String(f.id === filter));
    list.replaceChildren(
      ...byRecent(shown(works, filter, query)).map((w) => {
        const item = el('li');
        const link = el('a', w.name);
        link.href = address(tenant, w.id);
        item.append(link, el('span', ` ${KIND_WORDS[w.kind] ?? w.kind}`, 'caption'));
        const edited = editedWords(w.edited);
        if (edited) item.append(el('span', ` · ${edited}`, 'caption'));
        return item;
      }),
    );
    count.textContent = `${list.children.length} of ${works.length} ${works.length === 1 ? 'work' : 'works'}`;
    empty.replaceChildren();
    if (works.length === 0) {
      empty.append(
        regionState(`${BRANDING_CSS_URL}/icons.svg`, {
          kind: 'empty',
          noun: 'writing',
          title: 'Nothing written yet',
          text: 'Start writing, and the first page opens at once.',
        }),
      );
    } else if (list.children.length === 0) {
      empty.append(
        regionState(`${BRANDING_CSS_URL}/icons.svg`, { kind: 'empty-search', noun: 'writing' }),
      );
    }
  }

  const reviews = el('section');
  if (shared.length > 0) {
    reviews.append(el('h2', 'Shared with you to review'));
    const reviewList = el('ul', '', 'list');
    for (const share of shared) {
      const item = el('li');
      const link = el('a', share.name);
      link.href = `/?${new URLSearchParams({ tenant: share.tenant_id, review: share.edition_id })}`;
      item.append(link);
      reviewList.append(item);
    }
    reviews.append(reviewList);
  }

  body.replaceChildren(...(resume ? [resumeLine] : []), bar, search, count, list, empty, reviews);
  paint();
}
