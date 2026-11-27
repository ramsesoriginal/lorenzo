// "Where it appears" (BN11): what links to a being or a Fact - the Sessions and Scenes that name it
// and the other entries that do - and, for a being, the way to the scenes it lived through. The
// read is the one that shows each viewer only the information they may see (ADR 0110).

import { type Appearance, groupAppearances, takingPart } from '../../lib/appears';
import { livedOrderUrl, loadAppLinks, sceneUrl, sessionUrl } from '../../lib/appLinks';
import { getBacklinks, getBeingSessions } from '../../lib/descriptions';
import { getEntityDetail } from '../../lib/entities';
import { beingPageHref, entityHref, factPageHref } from '../../lib/entityLinks';

function element<K extends keyof HTMLElementTagNameMap>(tag: K, text = '', className = '') {
  const node = document.createElement(tag);

  node.textContent = text;
  node.className = className;
  return node;
}

function group(title: string, rows: Appearance[], href: (row: Appearance) => string | null) {
  const section = element('section', '', 'stack-tight');
  const list = element('ul', '', 'list');

  section.append(element('h2', `${title} `));
  section.querySelector('h2')?.append(element('span', String(rows.length), 'caption'));

  for (const row of rows) {
    const item = element('li');
    const where = href(row);
    const name = where ? element('a', row.name) : element('span', row.name);

    if (name instanceof HTMLAnchorElement && where) name.href = where;
    item.append(name, ' ', element('span', row.titles.join(', '), 'caption'));
    list.append(item);
  }

  section.append(list);
  return section;
}

export async function renderAppearsPage(
  root: HTMLElement,
  tenantId: string,
  tenantAddress: string,
  entityId: string,
): Promise<void> {
  const [entity, links] = await Promise.all([
    getEntityDetail(tenantId, entityId),
    getBacklinks(tenantId, entityId),
    loadAppLinks(),
  ]);
  const isFact = entity.kinds.includes('fact');
  // The Sessions a being came to or a Scene tells of it, which no text of theirs names (ADR 0531).
  const taking = isFact
    ? []
    : takingPart(await getBeingSessions(tenantId, entityId).catch(() => []));
  const back = element('a', `← ${entity.name}`);
  const found = groupAppearances(links);

  back.href = isFact
    ? factPageHref(tenantAddress, entityId)
    : beingPageHref(tenantAddress, { entity_id: entityId, slug: entity.slug });
  back.dataset.back = '';

  root.replaceChildren(
    back,
    element('h1', `Where ${entity.name} appears`, 'display'),
    element(
      'p',
      'Everything written that links here: the Sessions and Scenes that name it, and the other ' +
        'entries. You see only what you may read.',
      'status-text',
    ),
  );

  if (!isFact) {
    const lived = livedOrderUrl(tenantId, entityId);

    if (lived) {
      const link = element('a', 'See the scenes it lived through, in order');

      link.href = lived;
      link.dataset.lived = '';
      root.append(element('p'));
      root.lastElementChild?.append(link);
    }
  }

  const total = taking.length + found.sessions.length + found.scenes.length + found.others.length;

  if (total === 0) {
    root.append(element('p', 'Nothing links here yet.', 'status-text'));
  }

  const groups: [string, Appearance[], (row: Appearance) => string | null][] = [
    ['Sessions it takes part in', taking, (row) => sessionUrl(tenantId, row.entityId)],
    [
      isFact ? 'Sessions' : 'Sessions that name it',
      found.sessions,
      (row) => sessionUrl(tenantId, row.entityId),
    ],
    ['Scenes', found.scenes, (row) => sceneUrl(tenantId, row.entityId)],
    [
      'Other entries',
      found.others,
      (row) => entityHref(tenantAddress, { entity_id: row.entityId, kinds: row.kinds }),
    ],
  ];

  for (const [title, rows, href] of groups) {
    if (rows.length > 0) root.append(group(title, rows, href));
  }

  root.hidden = false;
}
