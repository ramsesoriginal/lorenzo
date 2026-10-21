import { fetchAllPages, type LorenzoClient, type Schema, unwrap } from '@lorenzo/api-client';
import { MAX_SELECTION, type Picked } from './model';

export type YearPreview = Schema<'YearPreview'>;
export type SavedPeriod = Schema<'PeriodDetailOut'>;

export type CalendarChoice = { id: string; name: string };

/** The calendars the person may read in a library or repository. */
export async function loadCalendars(
  client: LorenzoClient,
  tenantId: string,
): Promise<CalendarChoice[]> {
  const calendars = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/calendars', {
        params: { path: { tenant_id: tenantId }, query: { page, size: 100 } },
      }),
    ),
  );

  return calendars.map((calendar) => ({ id: calendar.entity_id, name: calendar.name }));
}

/**
 * The year a calendar is anchored to, where it has one, so a picker opens on a year that means
 * something there; otherwise zero. It is not "today": calendars have none (ADR 0308).
 */
export async function referenceYear(
  client: LorenzoClient,
  tenantId: string,
  calendarId: string,
): Promise<number> {
  const calendar = await unwrap(
    await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: calendarId } },
    }),
  );
  const year = (calendar.definition as { week?: { reference?: { year?: number } } }).week?.reference
    ?.year;

  return typeof year === 'number' ? year : 0;
}

export type YearView = {
  preview: YearPreview;
  /** The ids of the periods already saved in this year, by "segment|day" ("|" for the year). */
  saved: Map<string, string>;
};

export function savedKey(segment?: string, day?: number): string {
  return `${segment ?? ''}|${day ?? ''}`;
}

/** A year as the API calculates it, and which of its periods exist. Nothing is created. */
export async function loadYear(
  client: LorenzoClient,
  tenantId: string,
  calendarId: string,
  year: number,
): Promise<YearView> {
  const [preview, periods] = await Promise.all([
    client
      .GET('/tenants/{tenant_id}/calendars/{entity_id}/years/{year}', {
        params: { path: { tenant_id: tenantId, entity_id: calendarId, year } },
      })
      .then(unwrap),
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/calendar-periods', {
          params: {
            path: { tenant_id: tenantId },
            query: { calendar_id: calendarId, year, page, size: 100 },
          },
        }),
      ),
    ),
  ]);
  const saved = new Map<string, string>();

  for (const period of periods) {
    saved.set(savedKey(period.segment ?? undefined, period.day ?? undefined), period.entity_id);
  }

  return { preview, saved };
}

/** Periods by id, with their calendar and coordinates (the API takes a hundred at a time). */
export async function loadPeriods(
  client: LorenzoClient,
  tenantId: string,
  ids: readonly string[],
): Promise<SavedPeriod[]> {
  const found: SavedPeriod[] = [];

  for (let start = 0; start < ids.length; start += 100) {
    const chunk = ids.slice(start, start + 100);
    const page = await unwrap(
      await client.GET('/tenants/{tenant_id}/calendar-periods', {
        params: { path: { tenant_id: tenantId }, query: { id: chunk, size: 100 } },
      }),
    );

    found.push(...page.items);
  }

  return found;
}

/**
 * The ids of the chosen periods, in the order chosen, creating the ones that do not exist yet
 * (and their year and month parents) in one write per calendar. This is the only place the
 * picker writes, and only when the person saves.
 */
export async function materializeSelection(
  client: LorenzoClient,
  tenantId: string,
  selection: readonly Picked[],
): Promise<string[]> {
  if (selection.length > MAX_SELECTION) throw new Error(`Choose at most ${MAX_SELECTION} dates.`);

  const missing = selection.filter((picked) => picked.periodId === undefined);
  const ids = new Map<Picked, string>();

  for (const calendarId of new Set(missing.map((picked) => picked.coordinate.calendarId))) {
    const group = missing.filter((picked) => picked.coordinate.calendarId === calendarId);
    const created = await unwrap(
      await client.POST('/tenants/{tenant_id}/calendars/{calendar_id}/periods/batch', {
        params: { path: { tenant_id: tenantId, calendar_id: calendarId } },
        body: {
          periods: group.map(({ coordinate }) => ({
            year: coordinate.year,
            segment: coordinate.segment ?? null,
            day: coordinate.day ?? null,
            is_public: false,
          })),
        },
      }),
    );

    group.forEach((picked, index) => {
      const period = created[index];

      if (period) ids.set(picked, period.entity_id);
    });
  }

  return selection.map((picked) => {
    const id = picked.periodId ?? ids.get(picked);

    if (!id) throw new Error('A chosen date could not be saved.');

    return id;
  });
}
