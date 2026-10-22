import { type AppLinks, fill } from './appLinks';
import { type LorenzoClient, unwrap } from './index';

export type CalendarLink = { href: string; text: string; title?: string };
export const isCalendarKind = (kinds: readonly string[]): boolean =>
  kinds.some((kind) => ['calendar', 'calendar_period', 'event', 'clock'].includes(kind));

/** Uses only a visible entry's already-read metadata. UUIDs remain internal identities. */
export function calendarEntryHref(
  registry: AppLinks | undefined,
  tenant: string,
  entry: { entity_id: string; slug?: string | null; kinds: readonly string[] },
  hint = '',
): string | null {
  if (!isCalendarKind(entry.kinds)) return null;
  const calendar = entry.kinds.includes('calendar') && (!hint || hint === 'calendar');
  const key = calendar ? 'calendar' : 'calendar_entry';
  const named = entry.slug ? registry?.links[`${key}_by_slug`] : undefined;
  const template = named ?? registry?.links[key];
  return template ? fill(template, { tenant, id: entry.entity_id, slug: entry.slug ?? '' }) : null;
}

/** Batch bounded, permission-aware computed links. Never materializes dates. */
export async function calendarDateLinks(
  client: LorenzoClient,
  registry: AppLinks | undefined,
  tenantId: string,
  expressions: readonly string[],
  tenantAddress = tenantId,
): Promise<Map<string, CalendarLink>> {
  const result = new Map<string, CalendarLink>();
  const wanted = [...new Set(expressions)];
  for (let i = 0; i < wanted.length; i += 100) {
    const rows = await unwrap(
      await client.POST('/tenants/{tenant_id}/calendar-references/resolve', {
        params: { path: { tenant_id: tenantId } },
        body: { expressions: wanted.slice(i, i + 100) },
      }),
    );
    for (const row of rows) {
      const href = calendarEntryHref(registry, tenantAddress, {
        entity_id: row.calendar_entity_id,
        slug: row.calendar_slug,
        kinds: ['calendar'],
      });
      if (!href) continue;
      const url = new URL(href);
      url.searchParams.set('year', String(row.year));
      if (row.segment) url.searchParams.set('segment', row.segment);
      if (row.day !== null) url.searchParams.set('day', String(row.day));
      result.set(row.expression, { href: url.href, text: row.text });
    }
  }
  return result;
}
