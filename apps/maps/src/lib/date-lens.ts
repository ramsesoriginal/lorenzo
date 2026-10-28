// The date lens over the Maps list (ADR 0373): the shared period picker, one choice and read only,
// beside a way to leave out the Maps tied only to other dates. It opens empty, has no "today" and is
// not on the page at all when the library has no calendar.
import { createPeriodPicker, loadCalendars } from '@lorenzo/period-picker';
import '@lorenzo/period-picker/period-picker.css';
import { client } from './api';
import { type DateChoice, dateQuery } from './date-words';
import { el, field } from './dom';

export async function dateLens(tenant: string, changed: () => void) {
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
  const leave = field('Leave out Maps tied only to other dates', '', 'checkbox');
  const clear = el('button', 'Clear the date', 'btn btn-secondary');
  clear.type = 'button';
  leave.label.hidden = clear.hidden = true;
  clear.addEventListener('click', () => picker.setSelection([]));
  leave.input.addEventListener('change', changed);
  const root = el('div', '', 'stack-tight map-date-lens');
  root.append(picker.element, leave.label, clear);
  await picker.ready;

  return {
    element: root,
    /** The query the choice makes on the list. */
    query: () => dateQuery(choice, leave.input.checked),
    chosen: () => choice !== null,
    leavesOut: () => choice !== null && leave.input.checked,
  };
}
