import type { bindShell } from '@lorenzo/app-shell';
import { client } from './api';
import { el, entryHref, link, relationshipHref } from './dom';
import { listStats } from './matrix-api';
import { readEntry } from './social-api';
import { standingRows } from './standing-rows';
import { audienceWords } from './words';

type Shell = NonNullable<ReturnType<typeof bindShell>>;

type Edge = {
  id: string;
  name: string;
  can_manage?: boolean;
  can_edit?: boolean;
  is_public?: boolean | null;
  starts_at?: { id: string; name: string } | null;
  ends_at?: { id: string; name: string } | null;
};

/**
 * What the panel says of a relationship (SO2): its type, each standing with where it comes from, since
 * and until, the chain it holds through, and who may read it. Each part is read when the relationship
 * is selected; one that cannot be read leaves the others as they are.
 */
export async function relationshipPanel(
  tenant: string,
  edge: Edge,
  shell: Shell | null,
): Promise<HTMLElement> {
  const box = el('div', '', 'stack');
  const [entry, stats, through] = await Promise.all([
    readEntry(tenant, edge.id).catch(() => null),
    listStats(tenant).catch(() => []),
    client
      .GET('/tenants/{tenant_id}/relationships/{relationship_id}/through', {
        params: { path: { tenant_id: tenant, relationship_id: edge.id } },
        cache: 'no-cache',
      })
      .then((r) => (r.response.ok ? r.data : null))
      .catch(() => null),
  ]);

  box.append(
    el(
      'p',
      entry?.prototypes.length
        ? `Of the type ${entry.prototypes.map((p) => p.name).join(', ')}.`
        : 'It has no type.',
      'status-text',
    ),
  );

  if (edge.is_public !== null && edge.is_public !== undefined) {
    box.append(el('p', audienceWords(edge.is_public), 'status-text'));
  }

  // Time is optional: a relationship with neither behaves as if time did not exist.
  if (edge.starts_at || edge.ends_at) {
    const when = el('p', '', 'status-text');
    when.textContent = [
      edge.starts_at ? `Since ${edge.starts_at.name}` : '',
      edge.ends_at ? `until ${edge.ends_at.name}` : '',
    ]
      .filter(Boolean)
      .join(', ')
      .replace(/^./, (c) => c.toUpperCase())
      .concat('.');
    box.append(when);
  }

  box.append(
    standingRows({
      tenant,
      relationship: { id: edge.id, name: edge.name },
      entry,
      stats,
      canEdit: Boolean(edge.can_manage || edge.can_edit),
      shell,
    }),
  );

  if (through?.via.length) {
    const chain = el('ul', '', 'list');
    chain.setAttribute('aria-label', 'It holds through');
    for (const step of through.via) {
      const row = el('li');
      row.append(link(step.name, relationshipHref(tenant, step.id)));
      chain.append(row);
    }
    box.append(el('h3', 'It holds through', 'group-title'), chain);
  }
  return box;
}

/** What the panel says of an entry beyond its relationships: a group's members, apart from them (SO2). */
export async function membersPanel(tenant: string, id: string): Promise<HTMLElement | null> {
  const members = await client
    .GET('/tenants/{tenant_id}/groups/{group_entity_id}/members', {
      params: { path: { tenant_id: tenant, group_entity_id: id } },
      cache: 'no-cache',
    })
    .then((r) => (r.response.ok ? (r.data ?? []) : []))
    .catch(() => []);
  if (members.length === 0) return null;
  const box = el('div', '', 'stack-tight');
  const list = el('ul', '', 'list');
  list.setAttribute('aria-label', 'Its members');
  for (const m of members) {
    const row = el('li');
    row.append(link(m.name, entryHref(tenant, m.id)));
    list.append(row);
  }
  box.append(el('h3', 'Its members', 'group-title'), list);
  return box;
}
