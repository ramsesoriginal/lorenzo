import { client, fetchAllPages, type Schema, unwrap } from './api';
import type { Operation, Standing, StatLimits, Tie } from './matrix';

export type StatDef = Schema<'StatDefinitionOut'>;

/** The stats the library has, in their order: what a standing may be. */
export async function listStats(tenant: string): Promise<StatDef[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/stat-definitions', {
        params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
      }),
    ),
  );
}

export const limitsOf = (stat: StatDef): StatLimits => ({
  valueType: stat.value_type,
  min: stat.min_value ?? null,
  max: stat.max_value ?? null,
  name: stat.name,
});

/**
 * The relationships between the entries of a window, from the API: one-way and two-way ones in
 * either order, found through `end_a_in` and `end_b_in` (at most a hundred ids each). A
 * relationship the reader may not see is never in the answer.
 */
export async function readWindow(
  tenant: string,
  rows: readonly string[],
  cols: readonly string[],
  type: string | null,
): Promise<Tie[]> {
  const found = new Map<string, Tie>();
  for (const [first, second] of [
    [rows, cols],
    [cols, rows],
  ] as const) {
    if (first.length === 0 || second.length === 0) continue;
    const items = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/relationships', {
          params: {
            path: { tenant_id: tenant },
            query: {
              end_a_in: [...first],
              end_b_in: [...second],
              page,
              size: 100,
              ...(type ? { type } : {}),
            },
          },
          cache: 'no-cache',
        }),
      ),
    );
    for (const r of items) {
      found.set(r.id, {
        id: r.id,
        name: r.name,
        endA: r.end_a.id,
        endB: r.end_b.id,
        oneWay: r.one_way,
      });
    }
  }
  return [...found.values()];
}

/** The standing's value on every relationship the reader sees, by relationship id. */
export async function readStanding(tenant: string, stat: string): Promise<Map<string, Standing>> {
  const rows = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/effective-stats', {
        params: {
          path: { tenant_id: tenant },
          query: { stat_definition_id: [stat], kind: ['relationship'], page, size: 100 },
        },
        cache: 'no-cache',
      }),
    ),
  );
  const out = new Map<string, Standing>();
  for (const row of rows) {
    const found = row.stats.find((s) => s.stat_definition_id === stat);
    if (found && found.value !== null && found.value !== undefined) {
      out.set(row.id, { value: found.value as Standing['value'], own: found.own });
    }
  }
  return out;
}

/** A relationship's version, to address it by in a write. */
export async function versionOf(tenant: string, id: string): Promise<string> {
  const result = await client.GET('/tenants/{tenant_id}/relationships/{relationship_id}', {
    params: { path: { tenant_id: tenant, relationship_id: id } },
    cache: 'no-cache',
  });
  await unwrap(result);
  return result.response.headers.get('etag') ?? '';
}

/** Whether the library says a type is directed: its tag from the library-wide setting. */
export async function typeIsDirected(tenant: string, typeId: string): Promise<boolean> {
  const library = await unwrap(
    await client.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant } } }),
  );
  const directed = library.relationship_directed_stat_id;
  if (!directed) return false;
  const entry = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenant, entity_id: typeId } },
      cache: 'no-cache',
    }),
  );
  const stats = await listStats(tenant);
  const name = stats.find((s) => s.id === directed)?.name;
  return entry.stats.some((s) => s.name === name && s.value === true);
}

export interface BulkFailure {
  operation: number | null;
  status: number;
  detail: string;
}

/** One batch, all or nothing. A refusal says which operation, with the API's own reason. */
export async function writeBatch(
  tenant: string,
  operations: readonly Operation[],
): Promise<{ ok: true } | { ok: false; failure: BulkFailure }> {
  const result = await client.POST('/tenants/{tenant_id}/relationships/bulk', {
    params: { path: { tenant_id: tenant } },
    body: { operations: operations as never },
  });
  if (result.response.ok) return { ok: true };
  const problem = (result.error ?? {}) as { detail?: string; title?: string; operation?: number };
  return {
    ok: false,
    failure: {
      operation: typeof problem.operation === 'number' ? problem.operation : null,
      status: result.response.status,
      detail: problem.detail ?? problem.title ?? 'The batch was refused.',
    },
  };
}
