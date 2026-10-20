import { renderAudienceControl } from '@lorenzo/information-editor';
import { client, fetchAllPages, unwrap } from '../../lib/api';
import {
  attachExisting,
  createDatedEntry,
  createObservance,
  datedEntries,
} from '../../lib/dated-entries';
import { definitionEditor } from '../../lib/definition-editor';
import { button, el, entryHref, field, link, message, select } from '../../lib/dom';
import { informationView } from '../../lib/information';
import { start } from '../../lib/session';
import type { Period, YearPreview } from '../../lib/types';

const phases = [
  'New moon',
  'Waxing crescent',
  'First quarter',
  'Waxing gibbous',
  'Full moon',
  'Waning gibbous',
  'Last quarter',
  'Waning crescent',
];
export async function mount() {
  const session = await start();
  if (!session) return;
  const { tenantId, canWrite } = session;
  const host = document.querySelector('#CalendarView');
  if (!host) return;
  const params = new URLSearchParams(location.search);
  let id = params.get('id');
  const status = el('p');
  status.setAttribute('role', 'status');
  host.append(link('All calendars', `/?tenant=${encodeURIComponent(tenantId)}`), status);
  try {
    if (!id && params.get('slug')) {
      const resolved = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/resolve', {
          params: { path: { tenant_id: tenantId }, query: { slug: [params.get('slug') ?? ''] } },
        }),
      );
      id = resolved.find((r) => r.kinds.includes('calendar'))?.entity_id ?? null;
    }
    if (!id) throw new Error('Choose a calendar from your library.');
    const calendarId = id;
    const calendar = await unwrap(
      await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
        params: { path: { tenant_id: tenantId, entity_id: calendarId } },
      }),
    );
    host.append(el('h1', calendar.name));
    const tools = el('div', '', 'row');
    tools.append(link('Calendar information', entryHref(tenantId, calendarId)));
    host.append(tools);
    if (canWrite) {
      const edit = el('details');
      edit.append(
        el('summary', 'Edit calendar definition'),
        definitionEditor(tenantId, calendar),
        renderAudienceControl({ client, tenantId, entityId: calendarId }),
      );
      host.append(edit);
    }
    const fallback =
      calendar.definition.week?.reference.year ?? calendar.definition.moons[0]?.reference.year ?? 0;
    let year = params.has('year') ? Number(params.get('year')) : fallback;
    const y = field('Year', String(year), 'number');
    y.input.min = '-1000000';
    y.input.max = '1000000';
    const yearNav = el('form', '', 'row year-nav');
    const go = el('button', 'Open year', 'btn');
    go.type = 'submit';
    yearNav.append(
      button('Previous year', () => openYear(year - 1), true),
      y.label,
      go,
      button('Next year', () => openYear(year + 1), true),
    );
    host.append(yearNav);
    const body = el('div', '', 'calendar-layout');
    const grid = el('section', '', 'stack');
    const detail = el('aside', '', 'panel stack');
    detail.setAttribute('aria-live', 'polite');
    body.append(grid, detail);
    host.append(body);
    let preview: YearPreview;
    let periods: Period[] = [];
    let occurrences: Array<{
      entity_id: string;
      name: string;
      date: { year: number; segment: string; day: number };
    }> = [];
    let generation = 0;
    let selection = 0;
    yearNav.addEventListener('submit', (event) => {
      event.preventDefault();
      void openYear(Number(y.input.value));
    });
    async function openYear(next: number) {
      if (!Number.isInteger(next) || Math.abs(next) > 1000000) {
        status.textContent = 'Enter a whole year between −1000000 and 1000000.';
        return;
      }
      const turn = ++generation;
      status.textContent = 'Opening year…';
      try {
        const [calculated, saved, observances] = await Promise.all([
          unwrap(
            await client.GET('/tenants/{tenant_id}/calendars/{entity_id}/years/{year}', {
              params: { path: { tenant_id: tenantId, entity_id: calendarId, year: next } },
            }),
          ),
          fetchAllPages(async (page) =>
            unwrap(
              await client.GET('/tenants/{tenant_id}/calendars/{calendar_id}/periods', {
                params: {
                  path: { tenant_id: tenantId, calendar_id: calendarId },
                  query: { year: next, page, size: 100 },
                },
              }),
            ),
          ),
          fetchAllPages(async (page) =>
            unwrap(
              await client.GET(
                '/tenants/{tenant_id}/calendars/{calendar_id}/years/{year}/observances',
                {
                  params: {
                    path: { tenant_id: tenantId, calendar_id: calendarId, year: next },
                    query: { page, size: 100 },
                  },
                },
              ),
            ),
          ),
        ]);
        if (turn !== generation) return;
        year = next;
        y.input.value = String(year);
        preview = calculated;
        periods = saved;
        occurrences = observances;
        status.textContent = '';
        const url = new URL(location.href);
        url.searchParams.set('year', String(year));
        history.replaceState(null, '', url);
        showYear();
        await showPeriod();
      } catch (e) {
        if (turn === generation) status.textContent = message(e);
      }
    }
    function showYear() {
      grid.replaceChildren();
      const picker = select(
        'Month or festival',
        preview.segments.map((s) => [
          s.key,
          `${s.name}${s.kind === 'festival' ? ' · festival' : ''}`,
        ]),
        preview.segments[0]?.key ?? '',
      );
      const days = el('div');
      grid.append(
        button(`Year ${year}: notes and dated entries`, () => showPeriod(), true),
        picker.label,
        days,
      );
      picker.input.addEventListener('change', () => showSegment(picker.input.value, days));
      showSegment(picker.input.value, days);
    }
    function showSegment(key: string, container: HTMLElement) {
      const segment = preview.segments.find((s) => s.key === key);
      if (!segment) return;
      container.replaceChildren();
      container.append(
        el('h2', segment.name),
        button('Month or festival notes', () => showPeriod(key), true),
      );
      const definition = calendar.definition.segments.find((s) => s.key === key);
      const week = calendar.definition.week;
      const useWeek = Boolean(week && definition?.in_week);
      const cells = el('div', '', useWeek ? 'month-grid' : 'festival');
      cells.style.setProperty('--week-length', String(week?.length ?? 7));
      if (useWeek && calendar.definition.moons.length) {
        cells.classList.add('with-moons');
        cells.tabIndex = 0;
        cells.setAttribute('role', 'group');
        cells.setAttribute('aria-label', `Dates in ${segment.name} ${year}`);
        container.append(
          el('p', 'Scroll across the week for more dates.', 'caption calendar-scroll-hint'),
        );
      }
      if (useWeek && week) {
        for (let i = 0; i < week.length; i++)
          cells.append(el('span', week.names?.[i] ?? String(i + 1), 'weekday'));
        const start = segment.days[0]?.weekday ?? 0;
        for (let i = 0; i < start; i++) {
          const blank = el('span');
          blank.setAttribute('aria-hidden', 'true');
          cells.append(blank);
        }
      }
      for (const day of segment.days) {
        const cell = button(String(day.date.day), () => showPeriod(key, day.date.day), true);
        cell.className = 'day';
        cell.setAttribute('aria-label', `${day.date.day} ${segment.name} ${year}`);
        cell.dataset.day = String(day.date.day);
        if (periods.some((p) => p.segment === key && p.day === day.date.day)) {
          const mark = el('span', 'Notes and entries', 'caption');
          cell.append(mark);
        }
        for (const moon of calendar.definition.moons) {
          const phase = day.moons[moon.key];
          if (phase !== undefined)
            cell.append(el('span', `${moon.name}: ${phases[phase] ?? phase}`, 'moons'));
        }
        for (const occurrence of occurrences.filter(
          (o) => o.date.segment === key && o.date.day === day.date.day,
        ))
          cell.append(el('span', occurrence.name, 'caption'));
        cells.append(cell);
      }
      container.append(cells);
    }
    async function showPeriod(segment?: string, day?: number) {
      const turn = ++selection;
      const chosenYear = year;
      const title = segment
        ? `${day === undefined ? '' : `${day} `}${calendar.definition.segments.find((s) => s.key === segment)?.name ?? segment} ${year}`
        : `Year ${year}`;
      detail.replaceChildren(el('h2', title));
      const saved = periods.find((p) => p.segment === (segment ?? null) && p.day === (day ?? null));
      const localStatus = el('p');
      localStatus.setAttribute('role', 'status');
      let materialized = saved;
      async function materialize() {
        if (!materialized)
          materialized = await unwrap(
            await client.POST('/tenants/{tenant_id}/calendars/{calendar_id}/periods', {
              params: { path: { tenant_id: tenantId, calendar_id: calendarId } },
              body: {
                year: chosenYear,
                segment: segment ?? null,
                day: day ?? null,
                is_public: false,
              },
            }),
          );
        return materialized;
      }
      try {
        if (saved) {
          const entry = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: { tenant_id: tenantId, entity_id: saved.entity_id } },
            }),
          );
          const dates = await datedEntries(tenantId, saved.entity_id);
          if (turn !== selection) return;
          detail.append(
            link(
              'Open date entry',
              `${entryHref(tenantId, saved.entity_id)}&calendar=${encodeURIComponent(calendarId)}&year=${chosenYear}`,
            ),
            informationView(tenantId, entry, false, () => {}),
            dates,
          );
        } else
          detail.append(
            el(
              'p',
              'No notes or dated entries are available to you for this date.',
              'caption',
            ),
          );
        if (turn !== selection) return;
        for (const o of occurrences.filter(
          (o) =>
            (segment === undefined || o.date.segment === segment) &&
            (day === undefined || o.date.day === day),
        ))
          detail.append(
            link(
              `${o.date.day} ${calendar.definition.segments.find((s) => s.key === o.date.segment)?.name ?? o.date.segment}: ${o.name}`,
              entryHref(tenantId, o.entity_id),
            ),
          );
        if (canWrite) {
          detail.append(
            button(
              'Add information to this date',
              async () => {
                try {
                  const period = await materialize();
                  location.assign(
                    `${entryHref(tenantId, period.entity_id)}&calendar=${encodeURIComponent(calendarId)}&year=${chosenYear}&add=information`,
                  );
                } catch (e) {
                  localStatus.textContent = message(e);
                }
              },
              true,
            ),
          );
          const create = el('details');
          create.append(
            el('summary', 'Create a fact or story event'),
            createDatedEntry(tenantId, materialize),
          );
          const existing = el('details');
          existing.append(
            el('summary', 'Associate an existing fact or event'),
            attachExisting(tenantId, materialize),
          );
          detail.append(create, existing);
          if (segment && day !== undefined) {
            const recurring = el('details');
            recurring.append(
              el('summary', 'Create a recurring observance'),
              createObservance(tenantId, calendarId, calendar.definition, {
                segment,
                day,
                when: { every: 1, offset: 0 },
              }),
            );
            detail.append(recurring);
          }
        }
        detail.append(localStatus);
      } catch (e) {
        if (turn === selection) localStatus.textContent = message(e);
        detail.append(localStatus);
      }
    }
    await openYear(year);
  } catch (e) {
    status.textContent = message(e);
  }
}
