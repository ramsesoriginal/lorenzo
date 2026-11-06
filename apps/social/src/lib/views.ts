import {
  actions,
  audienceBadge,
  button,
  card,
  claim,
  el,
  empty,
  errorNotice,
  field,
  icon,
  link,
  loading,
  message,
  metaLine,
  pageHead,
  relationshipHref,
  say,
  sectionHead,
  select,
  statusLine,
  submit,
} from './dom';
import { canManage, libraryName, myLibraries } from './names';
import { entryPicker } from './pickers';
import { start } from './sign-in';

import {
  createRelationship,
  deleteRelationship,
  listRelationships,
  readEntry,
  readRelationship,
  replaceRelationship,
  setPublic,
} from './social-api';
import { readLibrary, readsOf } from './types-api';
import { audienceWords, defaultName, directionWords, sentence } from './words';

const tenantOf = () => new URLSearchParams(location.search).get('tenant');

/** Libraries first: a person opens Social from the library they are working in. */
export async function mountHome() {
  const host = document.querySelector<HTMLElement>('#social-home');
  if (!host || !claim(host)) return;
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening your libraries…'));
    const libraries = await myLibraries();
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Social', {
        lede: 'Who knows whom: the relationships of your libraries, and how much each one counts.',
      }),
    );
    if (libraries.length) {
      const list = el('ul', '', 'list');
      for (const library of libraries) {
        const row = el('li');
        const text = el('div', '', 'stack-tight grow');
        text.append(
          link(library.name, `/relationships/?${new URLSearchParams({ tenant: library.id })}`),
        );
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

/** The relationships of one library, searchable, and a form to make one. */
export async function mountRelationships() {
  const host = document.querySelector<HTMLElement>('#social-relationships');
  if (!host || !claim(host)) return;
  const tenant = tenantOf();
  if (!tenant) {
    location.replace('/');
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening the relationships…'));
    const [name, manage] = await Promise.all([libraryName(tenant), canManage(tenant)]);
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Relationships', {
        crumbs: [link('Libraries', '/')],
        lede: name ? `In ${name}.` : undefined,
      }),
    );

    const listing = el('section', '', 'stack');
    const list = el('ul', '', 'list');
    list.setAttribute('aria-label', 'Relationships');
    const status = statusLine();
    const more = el('div', '', 'row');
    let page = 1;
    let query = '';
    let total = 0;
    let shown = 0;

    const load = async (fresh: boolean) => {
      if (fresh) {
        page = 1;
        shown = 0;
        list.replaceChildren();
      }
      say(status, 'Reading the relationships…');
      try {
        const result = await listRelationships(tenant, { page, q: query });
        total = result.total ?? result.items.length;
        for (const row of result.items) {
          const item = el('li');
          const text = el('div', '', 'stack-tight grow');
          const title = el('div', '', 'row-tight');
          title.append(icon('kind-relationship'), link(row.name, relationshipHref(tenant, row.id)));
          text.append(title);
          text.append(
            el(
              'span',
              directionWords({
                endA: row.end_a.name,
                endB: row.end_b.name,
                oneWay: row.one_way,
              }),
              'status-text',
            ),
          );
          item.append(text);
          if (row.is_public !== null && row.is_public !== undefined) {
            item.append(audienceBadge(audienceWords(row.is_public), row.is_public));
          }
          list.append(item);
        }
        shown += result.items.length;
        say(
          status,
          total === 0
            ? query
              ? 'No relationship has that in its name.'
              : 'There are no relationships you can see yet.'
            : `Showing ${shown} of ${total}.`,
        );
        more.replaceChildren();
        if (shown < total) {
          more.append(
            button('Show more', async () => {
              page += 1;
              await load(false);
            }),
          );
        }
      } catch (error) {
        say(status, message(error), true);
      }
    };

    const search = el('form', '', 'row');
    const find = field('Find by name');
    find.input.type = 'search';
    search.append(find.label, submit('Find', 'secondary'));
    search.addEventListener('submit', (event) => {
      event.preventDefault();
      query = find.input.value.trim();
      void load(true);
    });
    listing.append(sectionHead('All relationships', { actions: [] }), search, list, status, more);
    view.append(listing);

    view.append(creator(tenant, manage));
    host.replaceChildren(view);
    await load(true);
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}

/** The form that makes a relationship: two ends, how it goes, what it is, and who may see it. */
function creator(tenant: string, manage: boolean) {
  const section = el('section', '', 'stack');
  section.append(sectionHead('Make a relationship'));
  const form = el('form', '', 'stack');
  form.setAttribute('aria-label', 'Make a relationship');
  const first = entryPicker(tenant, 'First end', { exclude: () => second.value() });
  const second = entryPicker(tenant, 'Second end', { exclude: () => first.value() });
  const kind = entryPicker(tenant, 'Type of relationship (optional)');
  const direction = select('How it goes', [
    ['both', 'Both ways'],
    ['one', 'From the first end to the second'],
  ]);
  const named = field('Name (optional)');
  const visible = field('Everyone in the library may see it', '', 'checkbox');
  const status = statusLine();
  form.append(
    first.label,
    second.label,
    direction.label,
    kind.label,
    named.label,
    ...(manage
      ? [visible.label]
      : [
          el(
            'p',
            'A relationship you make is for a being of yours and the GMs: it starts restricted and you cannot open it.',
            'status-text',
          ),
        ]),
    actions(submit('Make the relationship')),
    status,
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const a = first.value();
    const b = second.value();
    if (!a || !b) {
      say(status, 'Choose both ends first.', true);
      return;
    }
    say(status, 'Making the relationship…');
    const type = kind.value();
    void createRelationship(tenant, {
      name: named.input.value.trim() || defaultName(first.name(), second.name(), kind.name()),
      end_a: a,
      end_b: b,
      one_way: direction.input.value === 'one',
      prototypes: type ? [type] : [],
      is_public: manage && visible.input.checked,
    })
      .then((made) => location.assign(relationshipHref(tenant, made.id)))
      .catch((error) => say(status, message(error), true));
  });
  section.append(form);
  return section;
}

/** One relationship: who it ties and how, what it is, what it holds, and who may see it. */
export async function mountRelationship() {
  const host = document.querySelector<HTMLElement>('#social-relationship');
  if (!host || !claim(host)) return;
  const params = new URLSearchParams(location.search);
  const tenant = params.get('tenant');
  const id = params.get('id');
  if (!tenant || !id) {
    location.replace('/');
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  const draw = async () => {
    try {
      host.replaceChildren(loading('Opening the relationship…'));
      const [{ relationship, version }, entry, manage] = await Promise.all([
        readRelationship(tenant, id),
        readEntry(tenant, id),
        canManage(tenant),
      ]);
      const ends = {
        endA: relationship.end_a.name,
        endB: relationship.end_b.name,
        oneWay: relationship.one_way,
      };
      const first = entry.prototypes[0];
      // The library's words for the type, when it set them (ADR 0400).
      const words = first
        ? await readsOf(tenant, (await readLibrary(tenant)).library, first.id).catch(() => null)
        : null;
      const type = first
        ? {
            name: first.name,
            readsAs: words?.readsAs ?? null,
            readsAsBack: words?.readsAsBack ?? null,
          }
        : null;
      const view = el('div', '', 'stack view');
      const meta: Node[] = [metaLine('social', directionWords(ends))];
      if (relationship.is_public !== null && relationship.is_public !== undefined) {
        meta.push(audienceBadge(audienceWords(relationship.is_public), relationship.is_public));
      }
      view.append(
        pageHead(relationship.name, {
          crumbs: [
            link('Libraries', '/'),
            link('Relationships', `/relationships/?${new URLSearchParams({ tenant })}`),
          ],
          lede: sentence(ends, type),
          meta,
        }),
      );

      const about = card();
      about.body.append(
        el('h2', 'What it is', 'group-title'),
        el(
          'p',
          entry.prototypes.length
            ? `Of the type ${entry.prototypes.map((p) => p.name).join(', ')}.`
            : 'It has no type yet.',
        ),
      );
      view.append(about.root);

      const stats = card();
      stats.body.append(el('h2', 'What it holds', 'group-title'));
      if (entry.stats.length) {
        const rows = el('ul', '', 'list');
        for (const stat of entry.stats) {
          const row = el('li');
          row.append(
            el('span', stat.name, 'grow'),
            el('span', String(stat.value), 'chip'),
            el('span', stat.own ? 'its own' : 'inherited', 'status-text'),
          );
          rows.append(row);
        }
        stats.body.append(rows);
      } else {
        stats.body.append(empty('It holds no standings.'));
      }
      view.append(stats.root);

      if (relationship.can_edit) view.append(manager(tenant, id, version, relationship, draw));
      host.replaceChildren(view);
    } catch (error) {
      host.replaceChildren(errorNotice(error));
    }
  };
  await draw();
}

/** What a person who writes relationships can do to this one. */
function manager(
  tenant: string,
  id: string,
  version: string,
  relationship: Awaited<ReturnType<typeof readRelationship>>['relationship'],
  redraw: () => Promise<void>,
) {
  const panel = card();
  const status = statusLine();
  const changeEnds = (body: { end_a: string; end_b: string; one_way: boolean }) => async () => {
    await replaceRelationship(tenant, id, version, body);
    await redraw();
  };
  const buttons = [
    button(
      'Swap the two ends',
      changeEnds({
        end_a: relationship.end_b.id,
        end_b: relationship.end_a.id,
        one_way: relationship.one_way,
      }),
    ),
    button(
      relationship.one_way ? 'Make it go both ways' : 'Make it go one way',
      changeEnds({
        end_a: relationship.end_a.id,
        end_b: relationship.end_b.id,
        one_way: !relationship.one_way,
      }),
    ),
    ...(relationship.is_public === null || relationship.is_public === undefined
      ? []
      : [
          button(
            relationship.is_public
              ? 'Restrict who may see it'
              : 'Let everyone in the library see it',
            async () => {
              await setPublic(tenant, id, !relationship.is_public);
              await redraw();
            },
          ),
        ]),
    button(
      'Delete it',
      async () => {
        if (!confirm(`Delete “${relationship.name}”? This cannot be undone.`)) return;
        await deleteRelationship(tenant, id, version);
        location.assign(`/relationships/?${new URLSearchParams({ tenant })}`);
      },
      { variant: 'danger' },
    ),
  ];
  panel.body.append(el('h2', 'Change it', 'group-title'), actions(...buttons), status);
  return panel.root;
}
