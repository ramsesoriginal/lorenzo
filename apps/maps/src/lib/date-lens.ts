// The date lens over the Maps list and the Locations list (ADR 0373, 0377): the shared period
// picker, one choice and read only, beside a way to leave out what is tied only to other dates. It
// opens empty, has no "today" and is not on the page at all when the library has no calendar.
import { createPeriodPicker, loadCalendars } from '@lorenzo/period-picker';
import '@lorenzo/period-picker/period-picker.css';
import { createTimeFilter } from '@lorenzo/time-filter';
import { client } from './api';
import { type DateChoice, dateQuery } from './date-words';
import { el, field } from './dom';

export async function dateLens(
  tenant: string,
  changed: () => void,
  what: 'Maps' | 'Locations' = 'Maps',
) {
  let calendars: { id: string }[] = [];
  try {
    calendars = await loadCalendars(client, tenant);
  } catch {
    // Without calendars it cannot be read; the list stands as it was.
  }
  if (calendars.length === 0) return null;
  let choice: DateChoice | null = null;
  const picker = createPeriodPicker({
    client,
    tenantId: tenant,
    mode: 'single',
    // Nothing is created: the choice is read for its coordinates and resolve() is never called,
    // so a day no one has saved can be looked at like any other.
    canCreate: true,
    label: 'Tied to a date',
    onChange(selection) {
      const picked = selection[0]?.coordinate;
      choice = picked
        ? {
            calendarId: picked.calendarId,
            year: picked.year,
            ...(picked.segment !== undefined ? { segment: picked.segment } : {}),
            ...(picked.day !== undefined ? { day: picked.day } : {}),
          }
        : null;
      leave.label.hidden = clear.hidden = !choice;
      changed();
    },
  });
  const leave = field(`Leave out ${what} tied only to other dates`, '', 'checkbox');
  const clear = el('button', 'Clear the date', 'btn btn-secondary');
  clear.type = 'button';
  leave.label.hidden = clear.hidden = true;
  clear.addEventListener('click', () => picker.setSelection([]));
  leave.input.addEventListener('change', changed);
  const root = el('div', '', 'stack-tight map-date-lens');
  // The strip of a year (CS2, CS7): one date on it, a day of the calendar and year chosen beside it.
  // The picker below still reaches a month or a whole year, which a day on the strip cannot say.
  const stripHost = el('div', '', 'stack-tight');
  const calendarSelect = el('select', '', 'select');
  calendarSelect.setAttribute('aria-label', 'Calendar for the date strip');
  for (const c of calendars as { id: string; name?: string }[]) {
    const option = el('option', c.name ?? c.id);
    option.value = c.id;
    calendarSelect.append(option);
  }
  const yearInput = el('input', '', 'input') as HTMLInputElement;
  yearInput.type = 'number';
  yearInput.setAttribute('aria-label', 'Year for the date strip');
  yearInput.value = '0';
  async function drawStrip() {
    const year = Number(yearInput.value);
    if (!Number.isInteger(year)) return;
    try {
      const calculated = await client
        .GET('/tenants/{tenant_id}/calendars/{entity_id}/years/{year}', {
          params: { path: { tenant_id: tenant, entity_id: calendarSelect.value, year } },
        })
        .then((r) => r.data);
      if (!calculated) return;
      const segments = calculated.segments.map((x) => ({
        key: x.key,
        name: x.name,
        days: x.days.length,
        festival: x.month_ordinal === null,
      }));
      const filter = createTimeFilter({
        mode: 'point',
        segments,
        onChange(range) {
          let at = range?.from ?? 0;
          let hit: (typeof segments)[number] | undefined;
          for (const seg of segments) {
            if (at <= seg.days) {
              hit = seg;
              break;
            }
            at -= seg.days;
          }
          picker.setSelection([]);
          choice = hit
            ? {
                calendarId: calendarSelect.value,
                year,
                segment: hit.key,
                day: at,
              }
            : null;
          leave.label.hidden = clear.hidden = !choice;
          changed();
        },
      });
      stripHost.replaceChildren(filter.element);
    } catch {
      stripHost.replaceChildren();
    }
  }
  for (const input of [calendarSelect, yearInput])
    input.addEventListener('change', () => void drawStrip());
  const strip = el('div', '', 'stack-tight');
  strip.append(calendarSelect, yearInput, stripHost);
  root.append(strip, picker.element, leave.label, clear);
  await picker.ready;
  await drawStrip();

  return {
    element: root,
    /** The query the choice makes on the list. */
    query: () => dateQuery(choice, leave.input.checked),
    chosen: () => choice !== null,
    leavesOut: () => choice !== null && leave.input.checked,
  };
}
