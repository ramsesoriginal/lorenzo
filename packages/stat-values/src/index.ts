// An entry's stat values (ADR 0263, ADR 0272): each stat's effective value, where it comes from, and
// the entry's own value written or cleared. Bool stats are tags and stay with the apps' tag editors.
// The calls take the app's client, so every app keeps its own token and base URL.
import {
  type components,
  fetchAllPages,
  type LorenzoClient,
  MAX_PAGE_SIZE,
  unwrap,
} from '@lorenzo/api-client';

export type EntityDetail = components['schemas']['EntityDetailOut'];

/** The entry with its stats, each with whether it is the entry's own (ADR 0111). */
export async function getEntityDetail(
  client: LorenzoClient,
  tenantId: string,
  entityId: string,
): Promise<EntityDetail> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}

export type StatDefinition = components['schemas']['StatDefinitionOut'];
export type StatValue = number | string;

/** One stat as the page shows it: what the item resolves to, and whether that is its own. */
export type StatRow = {
  definition: StatDefinition;
  group: string;
  value: StatValue | null;
  own: boolean;
};

/** What the person was looking at when they changed a stat, to notice if it moved since. */
export type Seen = Pick<StatRow, 'value' | 'own'>;

/** The value changed under the person between reading the item and saving. */
export class StatChangedError extends Error {
  constructor() {
    super('Someone changed this stat while you were editing. The current value is shown.');
    this.name = 'StatChangedError';
  }
}

/** Every stat that is not a tag, with the name of its group. */
export async function statDefinitions(
  client: LorenzoClient,
  tenantId: string,
): Promise<{ definition: StatDefinition; group: string }[]> {
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
  const names = new Map(groups.map((group) => [group.id, group.name]));

  return definitions
    .filter((definition) => definition.value_type !== 'bool')
    .map((definition) => ({ definition, group: names.get(definition.stat_group_id) ?? '' }))
    .sort(
      (a, b) =>
        a.group.localeCompare(b.group) || a.definition.name.localeCompare(b.definition.name),
    );
}

/** A stat definition with its group, as the library orders them (ADR 0278). */
export type VocabularyEntry = {
  definition: StatDefinition;
  group: string;
  groupId: string;
};

/**
 * Every stat definition, tags included, in the library's own order: its groups by position, and a
 * group's definitions by position, then name. For a sheet, which draws them the way the library set
 * them out (`statDefinitions` is for a picker, in alphabetical order).
 */
export async function statVocabulary(
  client: LorenzoClient,
  tenantId: string,
): Promise<VocabularyEntry[]> {
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
  const byId = new Map(groups.map((group) => [group.id, group]));

  return definitions
    .map((definition) => ({
      definition,
      group: byId.get(definition.stat_group_id)?.name ?? '',
      groupId: definition.stat_group_id,
    }))
    .sort(
      (a, b) =>
        (byId.get(a.groupId)?.position ?? 0) - (byId.get(b.groupId)?.position ?? 0) ||
        a.group.localeCompare(b.group) ||
        a.definition.position - b.definition.position ||
        a.definition.name.localeCompare(b.definition.name),
    );
}

/** The rows for an item: every stat, with what it resolves to if it has a value at all. */
export function statRows(
  definitions: { definition: StatDefinition; group: string }[],
  entity: Pick<EntityDetail, 'stats'>,
): StatRow[] {
  const stats = new Map(entity.stats.map((stat) => [stat.name, stat]));

  return definitions.map(({ definition, group }) => {
    const stat = stats.get(definition.name);
    const value = typeof stat?.value === 'boolean' ? null : (stat?.value ?? null);

    return { definition, group, value, own: stat?.own === true };
  });
}

/** Where a row's value comes from, in words; `noun` is what the stat belongs to ("item", "being"). */
export function sourceIn(noun: string, row: Pick<StatRow, 'value' | 'own'>): string {
  if (row.own) return `Set on this ${noun}`;
  return row.value === null ? 'Not set' : 'Inherited';
}

/** `sourceIn` for an item, which is what the first app to show it had. */
export const sourceOf = (row: Pick<StatRow, 'value' | 'own'>): string => sourceIn('item', row);

/**
 * What typing gives for a stat: a whole number, a decimal (a point or a comma, no exponent), text,
 * or one of an enum's values. A problem comes back as words for the person.
 */
export function parseStat(
  definition: Pick<StatDefinition, 'value_type' | 'enum_values'>,
  text: string,
): { value: StatValue } | { problem: string } {
  const typed = text.trim();

  switch (definition.value_type) {
    case 'int':
      return /^-?\d+$/.test(typed)
        ? { value: Number(typed) }
        : { problem: 'Enter a whole number.' };
    case 'float': {
      const decimal = typed.replace(',', '.');
      return /^-?\d+(\.\d+)?$/.test(decimal)
        ? { value: Number(decimal) }
        : { problem: 'Enter a number, such as 2.5.' };
    }
    case 'enum':
      return definition.enum_values.includes(text)
        ? { value: text }
        : { problem: 'Choose one of the values.' };
    default:
      return typed ? { value: text } : { problem: 'Enter a value, or clear the stat.' };
  }
}

/** A decimal as JSON that keeps its point: the API refuses `3` for a decimal stat (ADR 0037). */
export function decimalText(value: number): string {
  return Number.isInteger(value) ? `${value}.0` : String(value);
}

/** The item as it is now; throws `StatChangedError` if the stat is no longer as it was seen. */
async function checkUnchanged(
  client: LorenzoClient,
  tenantId: string,
  entityId: string,
  definition: StatDefinition,
  seen: Seen,
): Promise<void> {
  const now = statRows(
    [{ definition, group: '' }],
    await getEntityDetail(client, tenantId, entityId),
  )[0] as StatRow;

  // Only its own value matters: what it inherits may differ without anyone having edited it.
  if (now.own !== seen.own || (now.own && now.value !== seen.value)) throw new StatChangedError();
}

/** Sets the item's own value for a stat; the item comes back. */
export async function setStat(
  client: LorenzoClient,
  tenantId: string,
  entityId: string,
  definition: StatDefinition,
  value: StatValue,
  seen: Seen,
): Promise<EntityDetail> {
  await checkUnchanged(client, tenantId, entityId, definition, seen);

  const path = '/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}';
  const params = {
    path: { tenant_id: tenantId, entity_id: entityId, stat_definition_id: definition.id },
  };

  // JSON written by the browser says `3` for `3.0`, which a decimal stat refuses: its body is
  // written by hand, point kept. `acquire_group` gives the item the stat's group (ADR 0142).
  if (definition.value_type === 'float' && typeof value === 'number') {
    return unwrap(
      await client.PUT(path, {
        params,
        body: { value: 0, acquire_group: true },
        bodySerializer: () => `{"value":${decimalText(value)},"acquire_group":true}`,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  }

  return unwrap(await client.PUT(path, { params, body: { value, acquire_group: true } }));
}

/** Removes the item's own value, so it inherits again; the item comes back. */
export async function clearStat(
  client: LorenzoClient,
  tenantId: string,
  entityId: string,
  definition: StatDefinition,
  seen: Seen,
): Promise<EntityDetail> {
  await checkUnchanged(client, tenantId, entityId, definition, seen);

  return unwrap(
    await client.DELETE('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: {
        path: { tenant_id: tenantId, entity_id: entityId, stat_definition_id: definition.id },
      },
    }),
  );
}
