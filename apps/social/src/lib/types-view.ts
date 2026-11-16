import { LorenzoApiError } from '@lorenzo/api-client';
import {
  actions,
  button,
  card,
  claim,
  el,
  empty,
  errorNotice,
  field,
  link,
  loading,
  message,
  pageHead,
  say,
  sectionHead,
  select,
  statusLine,
  submit,
} from './dom';
import { limitsOf, listStats, type StatDef } from './matrix-api';
import { canAdminister, canManage, libraryName } from './names';
import { start } from './sign-in';
import { STARTER_NOTE } from './starter-words';
import {
  addStarter,
  createStat,
  createType,
  ensureGroup,
  listTypes,
  readLibrary,
  saveScale,
  saveTypeStats,
  setStatValue,
  type TypeRow,
} from './types-api';
import { typeTree } from './types-tree';

/** The standings and types of a library, for those who write them. */
export async function mountTypes() {
  const host = document.querySelector<HTMLElement>('#social-types');
  if (!host || !claim(host)) return;
  const tenant = new URLSearchParams(location.search).get('tenant');
  if (!tenant) {
    location.replace('/');
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  const draw = async () => {
    try {
      host.replaceChildren(loading('Opening the types and standings…'));
      const [name, manage, admin, stats, types, { library }] = await Promise.all([
        libraryName(tenant),
        canManage(tenant),
        canAdminister(tenant),
        listStats(tenant),
        listTypes(tenant),
        readLibrary(tenant),
      ]);
      const view = el('div', '', 'stack view');
      view.append(
        pageHead('Types and standings', {
          crumbs: [
            link('Libraries', '/'),
            link('Relationships', `/relationships/?${new URLSearchParams({ tenant })}`),
          ],
          lede: name
            ? `The words relationships are told in, in ${name}.`
            : 'The words relationships are told in.',
        }),
      );
      const settingsSet = Boolean(
        library.relationship_reads_as_stat_id ||
          library.relationship_directed_stat_id ||
          library.relationship_reads_as_back_stat_id,
      );

      if (manage && admin && types.length === 0 && !settingsSet) {
        view.append(starterOffer(tenant, draw));
      }

      // How types point and read: three stats of the library, set by an administrator.
      const bools = stats.filter((s) => s.value_type === 'bool');
      const texts = stats.filter((s) => s.value_type === 'text');
      const how = card();
      how.body.append(el('h2', 'How types point and read', 'group-title'));
      how.body.append(
        el(
          'p',
          'A type may carry three stats: whether a relationship of it goes one way, and the words it reads as from each end. Without them a relationship reads with its type’s name.',
          'status-text',
        ),
      );
      const options = (list: StatDef[]): [string, string][] => [
        ['', 'None'],
        ...list.map((s) => [s.id, s.name] as [string, string]),
      ];
      const directed = select(
        'Goes one way (a tag)',
        options(bools),
        library.relationship_directed_stat_id ?? '',
      );
      const reads = select(
        'Reads as, from the first end (text)',
        options(texts),
        library.relationship_reads_as_stat_id ?? '',
      );
      const back = select(
        'Reads as, from the other end (text)',
        options(texts),
        library.relationship_reads_as_back_stat_id ?? '',
      );
      const howStatus = statusLine();
      how.body.append(directed.label, reads.label, back.label);
      if (admin) {
        how.body.append(
          actions(
            button('Save how types read', async () => {
              await saveTypeStats(tenant, {
                relationship_directed_stat_id: directed.input.value || null,
                relationship_reads_as_stat_id: reads.input.value || null,
                relationship_reads_as_back_stat_id: back.input.value || null,
              });
              say(howStatus, 'Saved how types read.');
            }),
          ),
        );
      } else {
        for (const control of [directed.input, reads.input, back.input]) control.disabled = true;
        how.body.append(el('p', 'An Owner or Organizer sets these.', 'status-text'));
      }
      how.body.append(howStatus);
      view.append(how.root);

      view.append(standingsSection(tenant, stats, manage, draw));
      view.append(typesSection(tenant, types, library, manage, draw));
      host.replaceChildren(view);
    } catch (error) {
      host.replaceChildren(errorNotice(error));
    }
  };
  await draw();
}

/** What an empty library is offered: the starter vocabulary, added on purpose. */
function starterOffer(tenant: string, redraw: () => Promise<void>) {
  const offer = card();
  const status = statusLine();
  offer.body.append(
    el('h2', 'Start from a set of types and standings', 'group-title'),
    el('p', STARTER_NOTE, 'status-text'),
    actions(
      button('Add the starter', async () => {
        const result = await addStarter(tenant, (text) => say(status, text));
        say(status, `Added ${result.made} types.`);
        await redraw();
      }),
    ),
    status,
  );
  return offer.root;
}

function standingsSection(
  tenant: string,
  stats: StatDef[],
  manage: boolean,
  redraw: () => Promise<void>,
) {
  const section = el('section', '', 'stack');
  const numbers = stats.filter((s) => s.value_type === 'int' || s.value_type === 'float');
  section.append(sectionHead('Standings', { count: numbers.length }));
  const list = el('ul', '', 'list');
  list.setAttribute('aria-label', 'Standings');
  for (const stat of numbers) {
    const limits = limitsOf(stat);
    const row = el('li');
    const text = el('div', '', 'stack-tight grow');
    text.append(
      el('span', stat.name, 'item-title'),
      el(
        'span',
        limits.min === null && limits.max === null
          ? 'No scale: any number.'
          : `From ${limits.min ?? 'any'} to ${limits.max ?? 'any'}.`,
        'status-text',
      ),
    );
    row.append(text);
    if (manage && stat.value_type === 'int') {
      const low = field('From', limits.min === null ? '' : String(limits.min), 'number');
      const high = field('To', limits.max === null ? '' : String(limits.max), 'number');
      const status = statusLine();
      const scale = el('div', '', 'row');
      scale.append(
        low.label,
        high.label,
        button(`Save the scale of ${stat.name}`, async () => {
          try {
            await saveScale(tenant, stat.id, {
              min: low.input.value === '' ? null : Number(low.input.value),
              max: high.input.value === '' ? null : Number(high.input.value),
            });
            await redraw();
          } catch (error) {
            const conflict = error instanceof LorenzoApiError && error.status === 409;
            say(status, conflict ? message(error) : message(error), true);
          }
        }),
      );
      row.append(scale, status);
    }
    list.append(row);
  }
  section.append(list);
  if (numbers.length === 0) section.append(empty('The library has no standings yet.'));
  if (manage) {
    const form = el('form', '', 'stack');
    form.setAttribute('aria-label', 'Add a standing');
    const named = field('Name of the standing');
    named.input.required = true;
    const low = field('From (optional)', '', 'number');
    const high = field('To (optional)', '', 'number');
    const status = statusLine();
    form.append(named.label, low.label, high.label, actions(submit('Add the standing')), status);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      void (async () => {
        try {
          const group = await ensureGroup(tenant);
          await createStat(tenant, group, {
            name: named.input.value.trim(),
            valueType: 'int',
            ...(low.input.value === '' ? {} : { min: Number(low.input.value) }),
            ...(high.input.value === '' ? {} : { max: Number(high.input.value) }),
          });
          await redraw();
        } catch (error) {
          say(status, message(error), true);
        }
      })();
    });
    section.append(form);
  }
  return section;
}

function typesSection(
  tenant: string,
  types: TypeRow[],
  library: Awaited<ReturnType<typeof readLibrary>>['library'],
  manage: boolean,
  redraw: () => Promise<void>,
) {
  const section = el('section', '', 'stack');
  section.append(sectionHead('Types of relationship', { count: types.length }));
  const list = el('ul', '', 'list');
  list.setAttribute('aria-label', 'Types of relationship');
  for (const { row, depth } of typeTree(types)) {
    const item = el('li');
    item.style.paddingInlineStart = `${depth * 1.5}rem`;
    const text = el('div', '', 'stack-tight grow');
    const reads = [row.reads_as, row.reads_as_back].filter(Boolean).join(' / ');
    text.append(
      el('span', row.name, 'item-title'),
      el(
        'span',
        [
          row.directed ? 'Goes one way.' : row.directed === false ? 'Goes both ways.' : '',
          reads ? `Reads as “${reads}”.` : '',
          row.in_use ? `${row.in_use} in use.` : '',
        ]
          .filter(Boolean)
          .join(' '),
        'status-text',
      ),
    );
    item.append(text);
    list.append(item);
  }
  section.append(list);
  if (types.length === 0) section.append(empty('The library has no types yet.'));
  if (manage) {
    const form = el('form', '', 'stack');
    form.setAttribute('aria-label', 'Make a type');
    const named = field('Name of the type');
    named.input.required = true;
    const parent = select('A kind of', [
      ['', 'Nothing: a type of its own'],
      ...types.map((t): [string, string] => [t.id, t.name]),
    ]);
    const oneWay = field('Goes one way', '', 'checkbox');
    const readsAs = field('Reads as, from the first end');
    const readsBack = field('Reads as, from the other end');
    const status = statusLine();
    form.append(
      named.label,
      parent.label,
      ...(library.relationship_directed_stat_id ? [oneWay.label] : []),
      ...(library.relationship_reads_as_stat_id ? [readsAs.label] : []),
      ...(library.relationship_reads_as_back_stat_id ? [readsBack.label] : []),
      actions(submit('Make the type')),
      status,
    );
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      void (async () => {
        try {
          const entry = await createType(
            tenant,
            named.input.value.trim(),
            parent.input.value ? [parent.input.value] : [],
          );
          const set = async (stat: string | null | undefined, value: string | boolean) => {
            if (stat && value !== '' && value !== false)
              await setStatValue(tenant, entry.id, stat, value);
          };
          await set(library.relationship_directed_stat_id, oneWay.input.checked);
          await set(library.relationship_reads_as_stat_id, readsAs.input.value.trim());
          await set(library.relationship_reads_as_back_stat_id, readsBack.input.value.trim());
          await redraw();
        } catch (error) {
          say(status, message(error), true);
        }
      })();
    });
    section.append(form);
  }
  return section;
}
