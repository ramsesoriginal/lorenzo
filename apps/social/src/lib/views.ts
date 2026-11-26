import { pageState } from '@lorenzo/app-shell';
import { BRANDING_CSS_URL } from './config';
import { formDialog } from './dialog';
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
import { listStats, type StatDef } from './matrix-api';
import { canManage, libraryName } from './names';
import { notes } from './notes';
import { endPicker, typePicker } from './pickers';
import { shellOf, start } from './sign-in';
import {
  createRelationship,
  deleteRelationship,
  listRelationships,
  readEntry,
  readRelationship,
  replaceRelationship,
  setPublic,
} from './social-api';
import { standingMark } from './standing';
import { readLibrary, readsOf } from './types-api';
import { audienceWords, defaultName, directionWords, sentence } from './words';

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

    const search = el('form', '', 'row');
    const find = field('Find by name');
    find.input.type = 'search';
    search.append(find.label, submit('Find', 'secondary'));
    search.addEventListener('submit', (event) => {
      event.preventDefault();
      query = find.input.value.trim();
      void load(true);
    });
    listing.append(
      sectionHead('All relationships', { actions: [] }),
      search,
      empties,
      list,
      status,
      more,
    );
    view.append(listing);

    host.replaceChildren(view);
    await load(true);
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}

/** The form that makes a relationship, in a dialog: two ends, how it goes, what it is, who may see it. */
function makeRelationship(tenant: string, manage: boolean) {
  const first = endPicker(tenant, 'First end', () => second.value());
  const second = endPicker(tenant, 'Second end', () => first.value());
  const kind = typePicker(tenant, 'Type of relationship (optional)');
  const direction = select('How it goes', [
    ['both', 'Both ways'],
    ['one', 'From the first end to the second'],
  ]);
  const named = field('Name (optional)');
  const visible = field('Everyone in the library may see it', '', 'checkbox');
  return formDialog({
    title: 'Make a relationship',
    submit: 'Make the relationship',
    fields: [
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
    ],
    async run() {
      const a = first.value();
      const b = second.value();
      if (!a || !b) throw new Error('Choose both ends first.');
      const type = kind.value();
      const made = await createRelationship(tenant, {
        name: named.input.value.trim() || defaultName(first.name(), second.name(), kind.name()),
        end_a: a,
        end_b: b,
        one_way: direction.input.value === 'one',
        prototypes: type ? [type] : [],
        is_public: manage && visible.input.checked,
      });
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
      );
      view.append(about.root);

      const stats = card();
      stats.body.append(el('h2', 'What it holds', 'group-title'));
      if (entry.stats.length) {
        const scales = new Map(
          (await listStats(tenant).catch((): StatDef[] => [])).map((def) => [def.id, def] as const),
        );
        const rows = el('ul', '', 'list');
        rows.setAttribute('aria-label', 'Standings');
        for (const stat of entry.stats) {
          const row = el('li');
          const def = scales.get(stat.stat_definition_id);
          row.append(
            el('span', stat.name, 'grow'),
            standingMark(
              stat.value,
              { min: def?.min_value ?? null, max: def?.max_value ?? null },
              stat.own ? 'direct' : 'inherited',
            ),
          );
          rows.append(row);
        }
        stats.body.append(rows);
      } else {
        stats.body.append(empty('It holds no standings.'));
      }
      view.append(stats.root);
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
