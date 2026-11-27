import { pageState } from '@lorenzo/app-shell';
import { fetchAllPages } from './api';
import { BRANDING_CSS_URL } from './config';
import { formDialog } from './dialog';
import {
  actions,
  audienceBadge,
  button,
  card,
  claim,
  el,
  entryHref,
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
  select,
  statusLine,
  submit,
} from './dom';
import { listStats, readStanding, type StatDef } from './matrix-api';
import { canManage, libraryName } from './names';
import { notes } from './notes';
import { endPicker } from './pickers';
import { relationshipForm } from './relationship-form';
import { timeAndChain } from './relationship-time';
import { shellOf, start } from './sign-in';
import {
  deleteRelationship,
  listRelationships,
  readEntry,
  readRelationship,
  replaceRelationship,
  setPublic,
} from './social-api';
import { standingMark } from './standing';
import { standingRows } from './standing-rows';
import { listTypes, readLibrary, readsOf } from './types-api';
import { audienceWords, directionWords, sentence } from './words';

const tenantOf = () => new URLSearchParams(location.search).get('tenant');

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
        lede: name ? `In ${name}.` : undefined,
        actions: [
          button('New relationship', () => makeRelationship(tenant, manage), {
            variant: 'primary',
            icon: 'add',
          }),
        ],
      }),
    );

    const listing = el('section', '', 'stack');
    const list = el('ul', '', 'list');
    list.setAttribute('aria-label', 'Relationships');
    const status = statusLine();
    const more = el('div', '', 'row');
    const empties = el('div');
    let page = 1;
    let query = '';
    let typeId = '';
    let endId = '';
    let statId = '';
    let atLeast: number | null = null;
    let atMost: number | null = null;
    let total = 0;
    let shown = 0;

    // The standing a row shows is the one asked for, or the library's first; read for all at once.
    let shownStanding: Promise<{
      def: StatDef;
      values: Map<string, { value: unknown; own: boolean }>;
    } | null> = Promise.resolve(null);
    const readRows = new Map<string, Promise<Awaited<ReturnType<typeof readEntry>> | null>>();
    const fillRow = async (rowId: string, kind: HTMLElement, mark: HTMLElement) => {
      let entry = readRows.get(rowId);
      if (!entry) {
        entry = readEntry(tenant, rowId).catch(() => null);
        readRows.set(rowId, entry);
      }
      const read = await entry;
      kind.textContent = read?.prototypes[0]?.name ?? '';
      const shown = await shownStanding;
      const value = shown?.values.get(rowId);
      if (shown && value && typeof value.value === 'number') {
        mark.replaceChildren(
          standingMark(
            value.value,
            { min: shown.def.min_value ?? null, max: shown.def.max_value ?? null },
            value.own ? 'direct' : 'inherited',
          ),
        );
      }
    };

    const load = async (fresh: boolean) => {
      if (fresh) {
        shownStanding = (async () => {
          const defs = (await listStats(tenant).catch((): StatDef[] => [])).filter(
            (x) => x.value_type === 'int',
          );
          const def = defs.find((x) => x.id === statId) ?? defs[0];
          return def ? { def, values: await readStanding(tenant, def.id) } : null;
        })().catch(() => null);
        page = 1;
        shown = 0;
        list.replaceChildren();
      }
      say(status, 'Reading the relationships…');
      try {
        const asked = {
          q: query,
          ...(typeId ? { type: typeId } : {}),
          ...(endId ? { end: endId } : {}),
        };
        // By standing: the list read has no such filter, so those that match are found here, whole.
        const result = statId
          ? await (async () => {
              const [all, values] = await Promise.all([
                fetchAllPages((p) => listRelationships(tenant, { page: p, ...asked })),
                readStanding(tenant, statId),
              ]);
              const items = all.filter((r) => {
                const v = values.get(r.id)?.value;
                return (
                  typeof v === 'number' &&
                  (atLeast === null || v >= atLeast) &&
                  (atMost === null || v <= atMost)
                );
              });
              return { items, total: items.length };
            })()
          : await listRelationships(tenant, { page, ...asked });
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
          // Its type and its standing, read once the row is there (the list read has neither).
          const kind = el('span', '', 'status-text');
          const mark = el('span');
          item.append(kind, mark);
          void fillRow(row.id, kind, mark);
          if (row.is_public !== null && row.is_public !== undefined) {
            item.append(audienceBadge(audienceWords(row.is_public), row.is_public));
          }
          list.append(item);
        }
        shown += result.items.length;
        const nothing = total === 0 && !query;
        empties.replaceChildren();
        if (nothing) {
          empties.append(
            pageState(BRANDING_CSS_URL, {
              art: 'empty-relationships',
              alt: 'Illustration: empty-relationships. No relationships yet',
              level: 2,
              title: 'There are no relationships you can see yet.',
              text: 'A relationship ties two beings or groups, and says how much it counts.',
              actions: [
                {
                  label: 'New relationship',
                  primary: true,
                  run: () => void makeRelationship(tenant, manage),
                },
              ],
            }),
          );
        }
        say(
          status,
          nothing
            ? ''
            : total === 0
              ? 'No relationship has that in its name.'
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

    // Find by name, and narrow by a type (and what inherits from it) or by an end: a being, or a group.
    const search = el('form', '', 'filters');
    search.setAttribute('aria-label', 'Find relationships');
    const find = field('Find by name');
    find.input.type = 'search';
    const typeRows = await listTypes(tenant).catch(() => []);
    const ofType = select('Of the type', [
      ['', 'Any type'],
      ...typeRows.map((t): [string, string] => [t.id, t.name]),
    ]);
    const withEnd = endPicker(tenant, 'With the entry or group');
    const narrow = el('div', '', 'row filters-actions');
    narrow.append(
      submit('Find', 'secondary'),
      button('Clear the filters', () => {
        for (const input of search.querySelectorAll<HTMLInputElement>('input')) input.value = '';
        for (const results of search.querySelectorAll<HTMLSelectElement>('select')) {
          results.hidden = true;
        }
        query = '';
        typeId = '';
        endId = '';
        statId = '';
        atLeast = null;
        atMost = null;
        byStanding.input.value = '';
        ofType.input.value = '';
        void load(true);
      }),
    );
    // By a standing: those with a value, and between two numbers if they are given.
    const numbers = (await listStats(tenant).catch((): StatDef[] => [])).filter(
      (x) => x.value_type === 'int',
    );
    const byStanding = select('Having the standing', [
      ['', 'Any standing'],
      ...numbers.map((x): [string, string] => [x.id, x.name]),
    ]);
    const least = field('At least', '', 'number');
    const most = field('At most', '', 'number');
    const range = el('div', '', 'row filters-range');
    range.append(least.label, most.label);
    search.append(
      find.label,
      ofType.label,
      withEnd.label,
      ...(numbers.length ? [byStanding.label, range] : []),
      narrow,
    );
    search.addEventListener('submit', (event) => {
      event.preventDefault();
      query = find.input.value.trim();
      typeId = ofType.input.value;
      endId = withEnd.value() ?? '';
      statId = byStanding.input.value;
      atLeast = least.input.value === '' ? null : Number(least.input.value);
      atMost = most.input.value === '' ? null : Number(most.input.value);
      void load(true);
    });
    listing.append(search, empties, list, status, more);
    view.append(listing);

    host.replaceChildren(view);
    await load(true);
    // The palette's "New relationship…" lands here with the form open.
    if (new URLSearchParams(location.search).get('new') === '1')
      void makeRelationship(tenant, manage);
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}

/** The form that makes a relationship, in a dialog; the new relationship's page opens after. */
function makeRelationship(tenant: string, manage: boolean) {
  const form = relationshipForm(tenant, manage);
  return formDialog({
    title: 'Make a relationship',
    submit: 'Make the relationship',
    fields: form.fields,
    async run() {
      const made = await form.submit();
      location.assign(relationshipHref(tenant, made.id));
    },
  });
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
      const [{ relationship, version }, entry, _manage] = await Promise.all([
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
          crumbs: [link('Relationships', `/relationships/?${new URLSearchParams({ tenant })}`)],
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
        el('h2', 'Its ends', 'group-title'),
      );
      const endsList = el('ul', '', 'list');
      endsList.setAttribute('aria-label', 'Its ends');
      for (const end of [relationship.end_a, relationship.end_b]) {
        const item = el('li');
        item.append(link(end.name, entryHref(tenant, end.id)));
        endsList.append(item);
      }
      about.body.append(endsList);
      view.append(about.root);

      const stats = card();
      stats.body.append(el('h2', 'What it holds', 'group-title'));
      stats.body.append(
        standingRows({
          tenant,
          relationship: { id, name: relationship.name },
          entry,
          stats: await listStats(tenant).catch((): StatDef[] => []),
          canEdit: relationship.can_edit,
          shell: shellOf(),
        }),
      );
      view.append(stats.root);
      view.append(
        ...(await timeAndChain(tenant, id, version, relationship, relationship.can_edit, draw)),
      );
      view.append(notes(tenant, id));

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
  const limits = {
    starts_at: relationship.starts_at?.id ?? null,
    ends_at: relationship.ends_at?.id ?? null,
  };
  const changeEnds = (body: { end_a: string; end_b: string; one_way: boolean }) => async () => {
    await replaceRelationship(tenant, id, version, { ...body, ...limits });
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
        const yes = await shellOf()?.confirm({
          title: `Delete “${relationship.name}”?`,
          body: 'The relationship and its notes go. The two entries stay as they are.',
          confirm: 'Delete it',
          danger: true,
        });
        if (!yes) return;
        await deleteRelationship(tenant, id, version);
        location.assign(`/relationships/?${new URLSearchParams({ tenant })}`);
      },
      { variant: 'danger' },
    ),
  ];
  panel.body.append(el('h2', 'Change it', 'group-title'), actions(...buttons), status);
  return panel.root;
}
