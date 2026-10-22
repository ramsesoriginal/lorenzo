import type { Schema } from '@lorenzo/api-client';
import { rememberEntryAddress } from './addresses';
import { client, fetchAllPages, unwrap } from './api';
import { button, check, el, entryHref, field, link, message, select } from './dom';
import { start } from './session';

type Range = Schema<'ReadingRange'>;
const readingText = (r: Range) =>
  r.lo === r.hi
    ? r.lo
    : `${r.lo_inclusive ? '[' : '('}${r.lo}, ${r.hi}${r.hi_inclusive ? ']' : ')'}`;
const dateText = (d: { year: number; segment: string; day: number }) =>
  `${d.year}/${d.segment}/${d.day}`;

// Clock editors retain drafts across conflicts. Refresh reads saved state without submitting it.
function editor(title: string) {
  const host = el('details', '', 'panel');
  const body = el('div', '', 'stack');
  const list = el('ul', '', 'stack-tight');
  const status = el('p');
  status.setAttribute('role', 'status');
  host.append(el('summary', title), body);
  body.append(list, status);
  let busy = false;
  const run = async (action: () => Promise<void>) => {
    if (busy || !host.isConnected) return;
    busy = true;
    body.inert = true;
    body.setAttribute('aria-busy', 'true');
    status.textContent = 'Saving…';
    try {
      await action();
    } catch (error) {
      status.textContent = `${message(error)} Your draft is kept. Refresh saved records to review changes before retrying.`;
    } finally {
      busy = false;
      body.inert = false;
      body.removeAttribute('aria-busy');
    }
  };
  return { host, body, list, status, run };
}

export async function mountClocks() {
  const host = document.querySelector<HTMLElement>('#ClockList');
  if (!host || host.dataset.mounted) return;
  host.dataset.mounted = 'true';
  const session = await start();
  if (!session || !host.isConnected) return;
  const tenant = session.tenantId;
  host.append(
    el('h1', 'Clocks'),
    link('All calendars', `/?tenant=${encodeURIComponent(tenant)}`),
    el(
      'p',
      'Keep each flow of time in its own reckoning. Clock readings never decide story order.',
      'intro',
    ),
  );
  const status = el('p');
  status.setAttribute('role', 'status');
  host.append(status);
  try {
    const clocks = await unwrap(
      await client.GET('/tenants/{tenant_id}/clocks', { params: { path: { tenant_id: tenant } } }),
    );
    if (!host.isConnected) return;
    const list = el('ul', '', 'calendar-list');
    for (const clock of clocks) {
      rememberEntryAddress(tenant, clock);
      const row = el('li', '', 'panel');
      row.append(
        link(clock.name, entryHref(tenant, clock.entity_id)),
        el('p', clock.ticking ? 'Ticking clock' : 'Timeless', 'caption'),
      );
      list.append(row);
    }
    host.append(list);
    if (!clocks.length)
      host.append(el('p', 'No clocks have been recorded here yet. Calendars work without them.'));
    if (session.canOrderEvents) {
      const form = el('details', '', 'panel');
      form.append(el('summary', 'Create a clock'));
      const creationId = crypto.randomUUID();
      const name = field('Clock name');
      const timeless = check('This clock is timeless');
      const shared = check('Everyone in this library can see this clock');
      const save = button('Create clock', async () => {
        save.disabled = true;
        try {
          const clock = await unwrap(
            await client.POST('/tenants/{tenant_id}/clocks', {
              params: { path: { tenant_id: tenant } },
              body: {
                id: creationId,
                name: name.input.value,
                ticking: !timeless.input.checked,
                is_public: shared.input.checked,
              },
            }),
          );
          rememberEntryAddress(tenant, clock);
          location.assign(entryHref(tenant, clock.entity_id));
        } catch (error) {
          status.textContent = `${message(error)} Your draft is kept.`;
        } finally {
          save.disabled = false;
        }
      });
      form.append(name.label, timeless.label, shared.label, save);
      host.append(form);
    }
  } catch (error) {
    status.textContent = message(error);
  }
}

async function calendarDateFields(tenant: string, calendarId: string) {
  const calendar = await unwrap(
    await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
      params: { path: { tenant_id: tenant, entity_id: calendarId } },
    }),
  );
  const year = field('Calendar year', '0', 'number');
  const segment = select(
    'Month or festival',
    calendar.definition.segments.map((s) => [s.key, s.name]),
    calendar.definition.segments[0]?.key ?? '',
  );
  const day = field('Calendar day', '1', 'number');
  return {
    nodes: [year.label, segment.label, day.label],
    value: () => ({
      year: Number(year.input.value),
      segment: segment.input.value,
      day: Number(day.input.value),
    }),
    set: (d: { year: number; segment: string; day: number }) => {
      year.input.value = String(d.year);
      segment.input.value = d.segment;
      day.input.value = String(d.day);
    },
  };
}

export async function clockPanel(tenant: string, id: string, canManage: boolean) {
  const ui = editor('Clock and calendar reckonings');
  const path = { tenant_id: tenant, clock_id: id };
  const response = await client.GET('/tenants/{tenant_id}/clocks/{clock_id}', { params: { path } });
  const clock = await unwrap(response);
  let clockVersion = response.response.headers.get('etag') ?? '';
  ui.body.prepend(
    el(
      'p',
      clock.ticking
        ? 'This clock has its own day readings.'
        : 'This clock is timeless. It has no readings or ratios.',
    ),
  );
  if (canManage) {
    const timeless = check('This clock is timeless', !clock.ticking);
    ui.body.append(
      timeless.label,
      button('Save clock', () =>
        ui.run(async () => {
          const saved = await client.PUT('/tenants/{tenant_id}/clocks/{clock_id}', {
            params: { path, header: { 'if-match': clockVersion } },
            body: { ticking: !timeless.input.checked },
          });
          await unwrap(saved);
          clockVersion = saved.response.headers.get('etag') ?? '';
          ui.status.textContent = 'Clock saved. Reopen this entry to refresh its editors.';
        }),
      ),
      button(
        'Refresh saved clock',
        () =>
          ui.run(async () => {
            const saved = await client.GET('/tenants/{tenant_id}/clocks/{clock_id}', {
              params: { path },
            });
            const value = await unwrap(saved);
            clockVersion = saved.response.headers.get('etag') ?? '';
            ui.status.textContent = `Saved clock: ${value.ticking ? 'ticking' : 'timeless'}. Your draft is kept.`;
          }),
        true,
      ),
    );
  }
  if (!clock.ticking) return ui.host;
  let version = '';
  let savedRows: Schema<'ReckoningOut'>[] = [];
  let editRow: ((row: Schema<'ReckoningOut'>) => Promise<void>) | null = null;
  async function read(fresh = false) {
    const result = await client.GET('/tenants/{tenant_id}/clocks/{clock_id}/reckonings', {
      cache: fresh ? 'no-store' : 'default',
      params: { path },
    });
    const rows = await unwrap(result);
    version = result.response.headers.get('etag') ?? '';
    savedRows = rows.items;
    ui.list.replaceChildren();
    for (const row of rows.items) {
      const li = el('li', '', 'stack-tight');
      li.append(
        el(
          'p',
          `${row.calendar_name}: ${dateText(row.date)} starts at ${row.reading}. ${row.is_shared ? 'Shared' : 'Private'}.`,
        ),
      );
      if (rows.can_manage)
        li.append(
          button(
            'Edit reckoning',
            async () => {
              await editRow?.(row);
            },
            true,
          ),
          button(
            'Remove reckoning',
            () =>
              ui.run(async () => {
                await unwrap(
                  await client.DELETE(
                    '/tenants/{tenant_id}/clocks/{clock_id}/reckonings/{calendar_id}',
                    {
                      params: {
                        path: { ...path, calendar_id: row.calendar_entity_id },
                        header: { 'if-match': version },
                      },
                    },
                  ),
                );
                await read();
                ui.status.textContent = 'Reckoning removed.';
              }),
            true,
          ),
        );
      ui.list.append(li);
    }
    if (!rows.items.length) ui.list.append(el('li', 'No calendar reckonings recorded.'));
  }
  await read();
  if (canManage) {
    const calendars = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/calendars', {
          params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
        }),
      ),
    );
    if (calendars.length) {
      const choose = select(
        'Reckoning calendar',
        calendars.map((c) => [c.entity_id, c.name]),
        calendars[0]?.entity_id ?? '',
      );
      const dates = el('div', '', 'row');
      let fields = await calendarDateFields(tenant, choose.input.value);
      dates.append(...fields.nodes);
      let generation = 0;
      const changeCalendar = async () => {
        const current = ++generation;
        const next = await calendarDateFields(tenant, choose.input.value);
        if (current !== generation) return;
        fields = next;
        dates.replaceChildren(...fields.nodes);
      };
      choose.input.addEventListener('change', () => {
        void ui.run(changeCalendar);
      });
      const anchor = field('Clock reading at the start of this date', '0');
      const shared = check('Share reckoning with readers of this clock and calendar');
      editRow = async (row) => {
        choose.input.value = row.calendar_entity_id;
        await changeCalendar();
        fields.set(row.date);
        anchor.input.value = row.reading;
        shared.input.checked = row.is_shared;
      };
      ui.body.append(
        choose.label,
        dates,
        anchor.label,
        shared.label,
        button('Save reckoning', () =>
          ui.run(async () => {
            await unwrap(
              await client.PUT('/tenants/{tenant_id}/clocks/{clock_id}/reckonings/{calendar_id}', {
                params: {
                  path: { ...path, calendar_id: choose.input.value },
                  header: { 'if-match': version },
                },
                body: {
                  date: fields.value(),
                  reading: anchor.input.value,
                  is_shared: shared.input.checked,
                },
              }),
            );
            await read();
            ui.status.textContent = 'Reckoning saved. Entered Event readings were kept.';
          }),
        ),
      );
    }
    ui.body.append(
      button(
        'Refresh saved records',
        () =>
          ui.run(async () => {
            await read(true);
            ui.status.textContent = `Saved reckonings refreshed (${savedRows.length}). Your draft is kept.`;
          }),
        true,
      ),
    );
  }
  return ui.host;
}

export async function eventReadings(tenant: string, event: string) {
  const ui = editor('Clock readings');
  const path = { tenant_id: tenant, event_id: event };
  let version = '';
  let editRow: ((row: Schema<'ReadingOut'>) => void) | null = null;
  async function read(fresh = false) {
    const result = await client.GET('/tenants/{tenant_id}/events/{event_id}/clock-readings', {
      cache: fresh ? 'no-store' : 'default',
      params: { path },
    });
    const rows = await unwrap(result);
    version = result.response.headers.get('etag') ?? '';
    ui.list.replaceChildren();
    for (const row of rows.items) {
      const li = el('li', '', 'stack-tight');
      li.append(
        el(
          'p',
          `${row.clock_name}: ${readingText(row.reading)} — Entered. ${row.is_shared ? 'Shared' : 'Private'}.`,
        ),
      );
      const calendars = await unwrap(
        await client.GET('/tenants/{tenant_id}/clocks/{clock_id}/reckonings', {
          params: { path: { tenant_id: tenant, clock_id: row.clock_entity_id } },
        }),
      );
      for (const reckoning of calendars.items)
        li.append(
          button(
            `Show dates in ${reckoning.calendar_name}`,
            () =>
              ui.run(async () => {
                const dates = await unwrap(
                  await client.POST('/tenants/{tenant_id}/clocks/{clock_id}/reading-dates', {
                    params: { path: { tenant_id: tenant, clock_id: row.clock_entity_id } },
                    body: {
                      calendar_entity_id: reckoning.calendar_entity_id,
                      reading: row.reading,
                    },
                  }),
                );
                ui.status.textContent = `${reckoning.calendar_name}: ${dateText(dates.first_date)} to ${dateText(dates.last_date)}. Calendar formatting of the entered reading.`;
              }),
            true,
          ),
        );
      if (rows.can_manage)
        li.append(
          button(
            'Edit reading',
            () => {
              editRow?.(row);
            },
            true,
          ),
          button(
            'Remove reading',
            () =>
              ui.run(async () => {
                await unwrap(
                  await client.DELETE(
                    '/tenants/{tenant_id}/events/{event_id}/clock-readings/{clock_id}',
                    {
                      params: {
                        path: { ...path, clock_id: row.clock_entity_id },
                        header: { 'if-match': version },
                      },
                    },
                  ),
                );
                await read();
                ui.status.textContent = 'Reading removed.';
              }),
            true,
          ),
        );
      ui.list.append(li);
    }
    if (!rows.items.length) ui.list.append(el('li', 'No permitted clock readings recorded.'));
    return rows.can_manage;
  }
  const canManage = await read();
  if (canManage) {
    const clocks = (
      await unwrap(
        await client.GET('/tenants/{tenant_id}/clocks', {
          params: { path: { tenant_id: tenant } },
        }),
      )
    ).filter((c) => c.ticking);
    if (clocks.length) {
      const choose = select(
        'Reading clock',
        clocks.map((c) => [c.entity_id, c.name]),
        clocks[0]?.entity_id ?? '',
      );
      const lo = field('Reading start');
      const hi = field('Reading end (leave empty for an exact point)');
      const includeLo = check('Include the start', true);
      const includeHi = check('Include the end', true);
      const shared = check('Share reading with readers of this Event and clock');
      const dateForm = el('details');
      dateForm.append(el('summary', 'Enter a calendar date'));
      const dateBody = el('div', '', 'stack');
      dateForm.append(dateBody);
      let dateGeneration = 0;
      const changeClock = async () => {
        const generation = ++dateGeneration;
        const clockId = choose.input.value;
        const rows = await unwrap(
          await client.GET('/tenants/{tenant_id}/clocks/{clock_id}/reckonings', {
            params: { path: { tenant_id: tenant, clock_id: clockId } },
          }),
        );
        if (generation !== dateGeneration) return;
        dateBody.replaceChildren();
        if (!rows.items.length) {
          dateBody.append(el('p', 'Add a calendar reckoning on this clock to enter a date.'));
          return;
        }
        const calendar = select(
          'Date calendar',
          rows.items.map((c) => [c.calendar_entity_id, c.calendar_name]),
          rows.items[0]?.calendar_entity_id ?? '',
        );
        const fieldsHost = el('div', '', 'row');
        let fields = await calendarDateFields(tenant, calendar.input.value);
        if (generation !== dateGeneration) return;
        fieldsHost.append(...fields.nodes);
        calendar.input.addEventListener('change', () => {
          void ui.run(async () => {
            fields = await calendarDateFields(tenant, calendar.input.value);
            fieldsHost.replaceChildren(...fields.nodes);
          });
        });
        dateBody.append(
          calendar.label,
          fieldsHost,
          button('Use this day', () =>
            ui.run(async () => {
              const result = await unwrap(
                await client.POST('/tenants/{tenant_id}/clocks/{clock_id}/date-reading', {
                  params: { path: { tenant_id: tenant, clock_id: clockId } },
                  body: { calendar_entity_id: calendar.input.value, date: fields.value() },
                }),
              );
              lo.input.value = result.reading.lo;
              hi.input.value = result.reading.hi;
              includeLo.input.checked = result.reading.lo_inclusive ?? true;
              includeHi.input.checked = result.reading.hi_inclusive ?? true;
              ui.status.textContent =
                'Day range prepared. Save the reading to record it on this Event.';
            }),
          ),
        );
      };
      choose.input.addEventListener('change', () => {
        void ui.run(changeClock);
      });
      editRow = (row) => {
        choose.input.value = row.clock_entity_id;
        lo.input.value = row.reading.lo;
        hi.input.value = row.reading.hi === row.reading.lo ? '' : row.reading.hi;
        includeLo.input.checked = row.reading.lo_inclusive ?? true;
        includeHi.input.checked = row.reading.hi_inclusive ?? true;
        shared.input.checked = row.is_shared;
        void ui.run(changeClock);
      };
      ui.body.append(
        choose.label,
        dateForm,
        lo.label,
        hi.label,
        includeLo.label,
        includeHi.label,
        shared.label,
        button('Save reading', () =>
          ui.run(async () => {
            await unwrap(
              await client.PUT('/tenants/{tenant_id}/events/{event_id}/clock-readings/{clock_id}', {
                params: {
                  path: { ...path, clock_id: choose.input.value },
                  header: { 'if-match': version },
                },
                body: {
                  reading: {
                    lo: lo.input.value,
                    hi: hi.input.value || lo.input.value,
                    lo_inclusive: includeLo.input.checked,
                    hi_inclusive: includeHi.input.checked,
                  },
                  is_shared: shared.input.checked,
                },
              }),
            );
            await read();
            ui.status.textContent = 'Reading saved. Story order was kept.';
          }),
        ),
      );
      await changeClock();
    } else ui.body.append(link('Create a clock', `/clocks/?tenant=${encodeURIComponent(tenant)}`));
    ui.body.append(
      button(
        'Refresh saved records',
        () =>
          ui.run(async () => {
            await read(true);
            ui.status.textContent = 'Saved readings refreshed. Your draft is kept.';
          }),
        true,
      ),
    );
  }
  return ui.host;
}
