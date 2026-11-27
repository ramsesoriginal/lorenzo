import {
  createTimeFilter,
  marksOfDays,
  periodQuery,
  type StripSegment,
  stripOf,
} from '@lorenzo/time-filter';
import { client, fetchAllPages, unwrap } from './api';
import { button, el, field, message, select, statusLine } from './dom';
import type { Picker } from './pickers';

const SIZE = 20;

/**
 * Choosing an Event for the date lens (SO4): the Events as the library tells its story, in story order
 * unless asked for by name, narrowed by when they are dated with the shared time filter (a calendar's
 * year, and a range of its days) and by name. The order is the API's: nothing here puts an Event
 * before another. A choice is one Event, told in words under the list.
 */
export function eventChooser(tenant: string, title: string): Picker {
  const label = el('fieldset', '', 'stack-tight');
  const legend = el('legend', title, 'field-label');
  const name = field('Find an Event by name');
  name.input.type = 'search';
  const order = select('Order', [
    ['order', 'In story order'],
    ['name', 'By name'],
  ]);
  const calendarChoice = select('Calendar', []);
  const year = field('Year', '', 'number');
  const timeHost = el('div', '', 'stack-tight');
  timeHost.hidden = true;
  const list = el('div', '', 'stack-tight');
  list.setAttribute('role', 'radiogroup');
  list.setAttribute('aria-label', `${title}: the Events`);
  const more = el('div', '', 'row');
  const status = statusLine();
  const chosen = el('p', 'Nothing chosen yet.', 'status-text');
  chosen.setAttribute('role', 'status');

  let picked: { id: string; name: string } | null = null;
  let page = 1;
  let range: { from: number; to: number } | null = null;
  let strip: StripSegment[] = [];
  let turn = 0;

  const load = async (fresh: boolean) => {
    const mine = ++turn;
    if (fresh) {
      page = 1;
      list.replaceChildren();
    }
    try {
      const result = await unwrap(
        await client.GET('/tenants/{tenant_id}/events', {
          params: {
            path: { tenant_id: tenant },
            query: {
              q: name.input.value,
              sort: order.input.value as 'name' | 'order',
              page,
              size: SIZE,
              ...periodQuery(calendarChoice.input.value, Number(year.input.value), strip, range),
            },
          },
          cache: 'no-cache',
        }),
      );
      if (mine !== turn) return;
      for (const event of result.items) {
        const row = el('label', '', 'check');
        const radio = el('input');
        radio.type = 'radio';
        radio.name = `event-${title}`;
        radio.value = event.entity_id;
        radio.checked = picked?.id === event.entity_id;
        radio.addEventListener('change', () => {
          picked = { id: event.entity_id, name: event.name };
          chosen.textContent = `Chosen: ${event.name}`;
        });
        const words = [event.name, event.dates?.length ? event.dates.join(' · ') : 'Undated'];
        row.append(radio, el('span', words.join(' — ')));
        list.append(row);
      }
      const shown = list.children.length;
      more.replaceChildren();
      if (shown < (result.total ?? shown)) {
        more.append(
          button('Show more Events', async () => {
            page += 1;
            await load(false);
          }),
        );
      }
      status.textContent = shown
        ? ''
        : range || name.input.value
          ? 'No Event matches.'
          : 'There are no Events you can see yet.';
    } catch (error) {
      status.textContent = message(error);
    }
  };

  // The strip: one calendar's year; a range of its days keeps the Events dated inside it.
  const drawStrip = async () => {
    const calendar = calendarChoice.input.value;
    strip = [];
    range = null;
    if (!calendar) {
      timeHost.hidden = true;
      return;
    }
    try {
      const read = await client
        .GET('/tenants/{tenant_id}/calendars/{entity_id}', {
          params: { path: { tenant_id: tenant, entity_id: calendar } },
        })
        .then((r) => r.data);
      if (!year.input.value) {
        const definition = read?.definition;
        // The year the calendar says it is in, else the one it is anchored to.
        year.input.value = String(
          read?.today?.year ??
            definition?.week?.reference.year ??
            definition?.moons[0]?.reference.year ??
            0,
        );
      }
      const chosenYear = Number(year.input.value);
      const calculated = await unwrap(
        await client.GET('/tenants/{tenant_id}/calendars/{entity_id}/years/{year}', {
          params: {
            path: { tenant_id: tenant, entity_id: calendar, year: chosenYear },
          },
        }),
      );
      strip = stripOf(calculated.segments);
      // A tick for each day Events are dated on, in one read of the year (ADR 0530).
      const marks = marksOfDays(
        await unwrap(
          await client.GET('/tenants/{tenant_id}/events/dated-days', {
            params: {
              path: { tenant_id: tenant },
              query: { calendar_id: calendar, year: chosenYear },
            },
          }),
        ).catch(() => []),
      );
      const today = read?.today?.year === chosenYear ? read.today : null;
      const filter = createTimeFilter({
        segments: strip,
        marks,
        today,
        onChange: (next) => {
          range = next;
          void load(true);
        },
      });
      const choosers = el('div', '', 'form-grid');
      choosers.append(
        ...(calendarChoice.input.options.length > 1 ? [calendarChoice.label] : []),
        year.label,
      );
      timeHost.replaceChildren(filter.element, choosers);
      timeHost.hidden = false;
    } catch (error) {
      timeHost.replaceChildren(
        el('p', `Could not draw the year. ${message(error)}`, 'status-text'),
      );
      timeHost.hidden = false;
    }
  };

  calendarChoice.input.addEventListener('change', () => {
    year.input.value = '';
    void drawStrip().then(() => load(true));
  });
  year.input.addEventListener('change', () => void drawStrip().then(() => load(true)));
  order.input.addEventListener('change', () => void load(true));
  let timer: ReturnType<typeof setTimeout> | undefined;
  name.input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => void load(true), 250);
  });

  label.append(legend, name.label, order.label, timeHost, list, more, status, chosen);

  // The calendars the library has, for the strip; with none there is no strip, and the list stands alone.
  void (async () => {
    const calendars = await fetchAllPages(async (n) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/calendars', {
          params: { path: { tenant_id: tenant }, query: { page: n, size: 100 } },
        }),
      ),
    ).catch(() => []);
    for (const c of calendars) {
      const option = el('option', c.name);
      option.value = c.entity_id;
      calendarChoice.input.append(option);
    }
    calendarChoice.input.value = calendars[0]?.entity_id ?? '';
    await drawStrip();
    await load(true);
  })();

  return {
    label,
    value: () => picked?.id ?? null,
    name: () => picked?.name ?? '',
  };
}
