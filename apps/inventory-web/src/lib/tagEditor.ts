// Three-state tag editing on the item page (ADR 0103, 0112): each bool stat
// in the tenant's `tags` group is inherited, on, or explicitly off. The editor itself is
// components/TagEditor.
import { client, type components, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import type { EntityDetail } from './types';

export type Definition = components['schemas']['StatDefinitionOut'];
export type State = 'inherited' | 'on' | 'off';

export const STATES: [State, string][] = [
  ['inherited', 'Inherited'],
  ['on', 'On'],
  ['off', 'Off'],
];

/**
 * A tag's state from the entity's effective stat (ADR 0111's `own`), and what inheriting
 * gives when that's what it does now; a value of its own hides what it would inherit.
 */
export function tagState(stat: EntityDetail['stats'][number] | undefined): {
  state: State;
  hint: string;
} {
  if (stat?.own) return { state: stat.value === true ? 'on' : 'off', hint: '' };
  const effective = !stat ? 'not set' : stat.value === true ? 'on' : 'off';
  return { state: 'inherited', hint: ` (${effective})` };
}

/** The tenant's tags: every bool definition in its `tags` group, by name. */
export async function tagDefinitions(tenantId: string): Promise<Definition[]> {
  const path = { tenant_id: tenantId };
  const query = (page: number) => ({ page, size: MAX_PAGE_SIZE });
  const [groups, definitions] = await Promise.all([
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/stat-groups', {
          params: { path, query: query(page) },
        }),
      ),
    ),
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/stat-definitions', {
          params: { path, query: query(page) },
        }),
      ),
    ),
  ]);
  const tags = groups.find((group) => group.name === 'tags');
  return definitions.filter((d) => d.stat_group_id === tags?.id && d.value_type === 'bool');
}

/** Sets a tag: PUT is on, PATCH explicitly off, DELETE back to inherited (ADR 0103). */
export async function setTag(
  tenantId: string,
  entityId: string,
  definitionId: string,
  state: State,
): Promise<EntityDetail> {
  const params = {
    path: { tenant_id: tenantId, entity_id: entityId, stat_definition_id: definitionId },
  };
  const path = '/tenants/{tenant_id}/entities/{entity_id}/tags/{stat_definition_id}';
  if (state === 'on') return unwrap(await client.PUT(path, { params }));
  if (state === 'off') return unwrap(await client.PATCH(path, { params }));
  return unwrap(await client.DELETE(path, { params }));
}
