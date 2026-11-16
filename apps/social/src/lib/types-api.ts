import { client, fetchAllPages, type Schema, unwrap } from './api';
import { listStats, type StatDef } from './matrix-api';
import { planStarter, STANDING_GROUP, STANDINGS, TYPE_STATS, TYPES } from './starter';

export type Library = Schema<'TenantOut'>;
export type TypeRow = Schema<'RelationshipTypeOut'>;

export async function readLibrary(tenant: string) {
  const result = await client.GET('/tenants/{tenant_id}', {
    params: { path: { tenant_id: tenant } },
    cache: 'no-cache',
  });
  const library = await unwrap(result);
  return { library, version: result.response.headers.get('etag') ?? '' };
}

/** The three stats that say how a type points and reads: a bool, then two text stats. */
export async function saveTypeStats(
  tenant: string,
  body: {
    relationship_directed_stat_id: string | null;
    relationship_reads_as_stat_id: string | null;
    relationship_reads_as_back_stat_id: string | null;
  },
) {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant } }, body }),
  );
}

export async function listTypes(tenant: string): Promise<TypeRow[]> {
  const read = await unwrap(
    await client.GET('/tenants/{tenant_id}/relationship-types', {
      params: { path: { tenant_id: tenant } },
      cache: 'no-cache',
    }),
  );
  return read.items;
}

export async function ensureGroup(tenant: string): Promise<string> {
  const groups = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/stat-groups', {
        params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
      }),
    ),
  );
  const found = groups.find((g) => g.name === STANDING_GROUP);
  if (found) return found.id;
  const made = await unwrap(
    await client.POST('/tenants/{tenant_id}/stat-groups', {
      params: { path: { tenant_id: tenant } },
      body: { name: STANDING_GROUP, priority: 0, mandatory: false },
    }),
  );
  return made.id;
}

export async function createStat(
  tenant: string,
  group: string,
  body: { name: string; valueType: 'int' | 'bool' | 'text'; min?: number; max?: number },
) {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/stat-definitions', {
      params: { path: { tenant_id: tenant } },
      body: {
        name: body.name,
        stat_group_id: group,
        value_type: body.valueType,
        adjustable_in_play: false,
        pin: false,
        signed: false,
        ...(body.min === undefined ? {} : { min_value: body.min }),
        ...(body.max === undefined ? {} : { max_value: body.max }),
      },
    }),
  );
}

/** Changes a standing's scale; a bound that values already break is a 409 with their number. */
export async function saveScale(
  tenant: string,
  stat: string,
  scale: { min: number | null; max: number | null },
) {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}/stat-definitions/{stat_definition_id}', {
      params: { path: { tenant_id: tenant, stat_definition_id: stat } },
      body: { min_value: scale.min, max_value: scale.max },
    }),
  );
}

export async function createType(tenant: string, name: string, parents: string[]) {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id: tenant } },
      body: { name, kinds: [], parents },
    }),
  );
}

export async function setStatValue(
  tenant: string,
  entity: string,
  stat: string,
  value: string | number | boolean,
) {
  return unwrap(
    await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: { path: { tenant_id: tenant, entity_id: entity, stat_definition_id: stat } },
      body: { value, acquire_group: true },
    }),
  );
}

/** How a type reads, from the library's settings and the type's own stats; none without them. */
export async function readsOf(
  tenant: string,
  library: Library,
  typeId: string,
): Promise<{ readsAs: string | null; readsAsBack: string | null }> {
  if (!library.relationship_reads_as_stat_id) return { readsAs: null, readsAsBack: null };
  const [stats, entry] = await Promise.all([
    listStats(tenant),
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenant, entity_id: typeId } },
        cache: 'no-cache',
      }),
    ),
  ]);
  const text = (id: string | null | undefined) => {
    const name = stats.find((s: StatDef) => s.id === id)?.name;
    const found = entry.stats.find((s) => s.name === name);
    return typeof found?.value === 'string' ? found.value : null;
  };
  return {
    readsAs: text(library.relationship_reads_as_stat_id),
    readsAsBack: text(library.relationship_reads_as_back_stat_id),
  };
}

/** Adds the starter: the group, the stats, the library's settings, then the types with their
 * words. A name the library already has is left alone, so a second run adds only what is missing. */
export async function addStarter(
  tenant: string,
  progress: (text: string) => void,
): Promise<{ made: number }> {
  const [stats, existing] = await Promise.all([listStats(tenant), listTypes(tenant)]);
  const plan = planStarter({
    statNames: new Set(stats.map((s) => s.name)),
    entryNames: new Set(existing.map((t) => t.name)),
  });
  progress('Making the stats…');
  const group = await ensureGroup(tenant);
  const byName = new Map(stats.map((s) => [s.name, s.id]));
  const ensure = async (
    name: string,
    valueType: 'int' | 'bool' | 'text',
    min?: number,
    max?: number,
  ) => {
    const known = byName.get(name);
    if (known) return known;
    const made = await createStat(tenant, group, {
      name,
      valueType,
      ...(min === undefined ? {} : { min }),
      ...(max === undefined ? {} : { max }),
    });
    byName.set(name, made.id);
    return made.id;
  };
  const directed = await ensure(TYPE_STATS.directed, 'bool');
  const readsAs = await ensure(TYPE_STATS.readsAs, 'text');
  const readsBack = await ensure(TYPE_STATS.readsAsBack, 'text');
  for (const s of STANDINGS)
    if (plan.standings.includes(s)) await ensure(s.name, 'int', s.min, s.max);
  progress('Setting how types point and read…');
  await saveTypeStats(tenant, {
    relationship_directed_stat_id: directed,
    relationship_reads_as_stat_id: readsAs,
    relationship_reads_as_back_stat_id: readsBack,
  });
  const ids = new Map(existing.map((t) => [t.name, t.id]));
  let made = 0;
  for (const type of TYPES) {
    if (ids.has(type.name)) continue;
    progress(`Making ${type.name}…`);
    const parent = type.parent ? ids.get(type.parent) : undefined;
    const entry = await createType(tenant, type.name, parent ? [parent] : []);
    ids.set(type.name, entry.id);
    made += 1;
    if (type.directed) await setStatValue(tenant, entry.id, directed, true);
    if (type.readsAs) await setStatValue(tenant, entry.id, readsAs, type.readsAs);
    if (type.readsAsBack) await setStatValue(tenant, entry.id, readsBack, type.readsAsBack);
  }
  return { made };
}
