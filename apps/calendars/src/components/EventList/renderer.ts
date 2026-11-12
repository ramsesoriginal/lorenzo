import { createTimeFilter, dayAt, type StripSegment } from '@lorenzo/time-filter';
import { rememberEntryAddress, tenantAddress } from '../../lib/addresses';
import { client, fetchAllPages, unwrap } from '../../lib/api';
import {
  button,
  disclosure,
  el,
  entryHref,
  feedback,
  field,
  icon,
  iconLink,
  link,
  message,
  select,
  submit,
} from '../../lib/dom';
import { entryPicker } from '../../lib/entry-picker';
import { creationVisibility } from '../../lib/event-visibility';
import { start } from '../../lib/session';

export async function mount() {
  const host = document.querySelector<HTMLElement>('#EventList');
  if (!host || host.dataset.mounted) return;
  host.dataset.mounted = 'true';
  const session = await start();
  if (!session || !host?.isConnected) return;
  const { tenantId, canOrderEvents, canReadEventOrder } = session;
  const initial = new URLSearchParams(location.search);
  let being = canOrderEvents ? (initial.get('being') ?? '') : '';
  let chain = initial.get('chain') ?? '';
  let page = 1;
  const head = el('div', '', 'page-heading');
  head.append(
    el('h1', 'Events'),
    el('p', 'Record what happened, even before its date is known.', 'page-sub'),
  );
  host.append(iconLink('All calendars', `/?tenant=${encodeURIComponent(tenantId)}`, 'back'), head);
  const status = feedback();
  const list = el('ol', '', 'list event-list');
  list.dataset.eventList = '';
  const nav = el('div', '', 'row');
  const q = field('Search Event names', initial.get('q') ?? '');
  const sort = select(
    'List order',
    canReadEventOrder
      ? [
          ['name', 'Name'],
          ['order', 'Story order'],
        ]
      : [['name', 'Name']],
    canReadEventOrder && initial.get('sort') === 'order' ? 'order' : 'name',
  );
  sort.input.setAttribute('aria-label', 'List order');
  const direction = select(
    'Causal direction',
    [
      ['both', 'What led here and followed'],
      ['ancestors', 'What led here'],
      ['descendants', 'What followed'],
    ],
    'both',
  );
  direction.input.setAttribute('aria-label', 'Causal direction');
  const filters = el('div', '', 'card card-body stack');
  const choices = el('p', '', 'caption');
  function showChoices() {
    choices.textContent = [
      being ? 'Participant filter selected' : '',
      chain ? 'Causal Event selected' : '',
    ]
      .filter(Boolean)
      .join(' · ');
  }
  // The strip's ticks need each Event's structured dates, read through the entry's own endpoints.
  type Dated = { calendar: string; year: number; segment: string | null; day: number | null };
  type Meta = { when: string; dates: Dated[]; who: string };
  const metaCache = new Map<string, Promise<Meta>>();
  function metaFor(id: string): Promise<Meta> {
    let known = metaCache.get(id);
    if (!known) {
      const path = { tenant_id: tenantId, entity_id: id };
      known = (async () => {
        const dates = await client
          .GET('/tenants/{tenant_id}/entities/{entity_id}/dates', { params: { path } })
          .then((r) => r.data ?? [])
          .catch(() => []);
        const who = canOrderEvents
          ? await client
              .GET('/tenants/{tenant_id}/events/{event_id}/participants', {
                params: { path: { tenant_id: tenantId, event_id: id } },
              })
              .then((r) => (r.data ?? []).map((b) => b.name))
              .catch(() => [])
          : [];
        return {
          when: dates.length ? dates.map((d) => d.name).join(' · ') : 'Undated',
          dates: dates.map((d) => ({
            calendar: d.calendar_entity_id,
            year: d.year,
            segment: d.segment,
            day: d.day,
          })),
          who: who.join(', '),
        };
      })();
      metaCache.set(id, known);
    }
    return known;
  }
  // The time filter (CS2): a strip of one calendar's year; a range of its days narrows the list to
  // the Events dated inside it. Which calendar and year it draws is chosen beside it.
  let range: { from: number; to: number } | null =
    initial.get('from') && initial.get('to')
      ? { from: Number(initial.get('from')), to: Number(initial.get('to')) }
      : null;
  let strip: StripSegment[] = [];
  let calendarId = initial.get('calendar') ?? '';
  const yearField = field('Year', initial.get('year') ?? '', 'number');
  yearField.label.classList.add('narrow-field');
  const calendarChoice = select('Calendar', [], calendarId);
  const timeHost = el('section', '', 'stack-tight');
  let stripReady: Promise<void> = Promise.resolve();
  let generation = 0;
  async function load() {
    const turn = ++generation;
    status.busy('Loading Events…');
    try {
      // The time filter is the API's (ADR 0442): the Events dated in the strip's year, or in the range on
      // it, through dates the reader can see, applied before the page and the story order.
      await stripReady;
      const ends = range ? [dayAt(strip, range.from), dayAt(strip, range.to)] : [];
      const response = await unwrap(
        await client.GET('/tenants/{tenant_id}/events', {
          params: {
            path: { tenant_id: tenantId },
            query: {
              q: q.input.value,
              sort: sort.input.value as 'name' | 'order',
              being_id: being || undefined,
              causal_event_id: chain || undefined,
              direction: direction.input.value as 'both' | 'ancestors' | 'descendants',
              page,
              size: 30,
              ...(range && calendarId && strip.length
                ? {
                    dated_calendar_id: calendarId,
                    dated_year: Number(yearField.input.value),
                    dated_from_segment: ends[0]?.key,
                    dated_from_day: ends[0]?.day,
                    dated_to_segment: ends[1]?.key,
                    dated_to_day: ends[1]?.day,
                  }
                : {}),
            },
          },
        }),
      );
      if (turn !== generation || !host?.isConnected) return;
      list.replaceChildren();
      list.hidden = !response.items.length;
      for (const [index, entry] of response.items.entries()) {
        rememberEntryAddress(tenantId, entry);
        const row = el('li', '', 'event-row');
        row.append(icon('kind-event', 'event-mark'));
        const open = link(entry.name, entryHref(tenantId, entry.entity_id));
        const text = el('div', '', 'event-text grow');
        const detail = el('span', '', 'caption event-meta');
        open.classList.remove('grow');
        text.append(open, detail);
        // The list says it itself (ADR 0442): where it is dated and, for who may read it, who took part.
        detail.textContent = [
          entry.dates?.length ? entry.dates.join(' · ') : 'Undated',
          entry.participants ? entry.participants.join(', ') || 'No one recorded' : '',
        ]
          .filter(Boolean)
          .join(' · ');
        row.append(text);
        if (entry.order_basis) {
          // What the story order rests on (D24): a chip with the place in the order, and the whole
          // sentence for a screen reader, which is what the old caption said.
          const words = {
            causal: 'Causal order',
            ruled: 'Recorded order',
            linearized: canOrderEvents
              ? 'Linearized · no recorded ordering path'
              : 'Linearized · no visible recorded ordering path',
          }[entry.order_basis];
          const position = sort.input.value === 'order' ? `${(page - 1) * 30 + index + 1}. ` : '';
          const chip = el('span', '', 'state-chip');
          chip.dataset.state = entry.order_basis === 'linearized' ? 'stale' : 'synced';
          chip.setAttribute('aria-hidden', 'true');
          chip.append(
            el(
              'span',
              `${position}${entry.order_basis === 'linearized' ? 'linearized' : 'recorded'}`,
            ),
          );
          row.append(chip, el('span', words, 'visually-hidden'));
        }
        if (canReadEventOrder) {
          const follow = button(
            'Follow causes',
            () => {
              chain = entry.entity_id;
              sort.input.value = 'order';
              page = 1;
              showChoices();
              void load();
            },
            true,
            'causality',
          );
          follow.classList.replace('btn-secondary', 'btn-text');
          row.append(follow);
        }
        list.append(row);
      }
      nav.replaceChildren();
      if (page > 1)
        nav.append(
          button(
            'Previous Events',
            () => {
              page--;
              void load();
            },
            true,
            'previous',
          ),
        );
      if (page < (response.pages ?? 0))
        nav.append(
          button(
            'Next Events',
            () => {
              page++;
              void load();
            },
            true,
            'next',
          ),
        );
      status.say(
        response.total
          ? `${response.total} Event${response.total === 1 ? '' : 's'}.`
          : 'No Events match these filters.',
      );
      const address = new URL(location.href);
      address.searchParams.set('tenant', tenantAddress(tenantId));
      for (const [key, value] of Object.entries({
        q: q.input.value,
        sort: sort.input.value,
        being,
        chain,
        calendar: range ? calendarId : '',
        year: range ? yearField.input.value : '',
        from: range ? String(range.from) : '',
        to: range ? String(range.to) : '',
      })) {
        if (value) address.searchParams.set(key, value);
        else address.searchParams.delete(key);
      }
      history.replaceState(history.state, '', address);
    } catch (error) {
      if (turn === generation) {
        list.replaceChildren();
        list.hidden = true;
        status.fail(message(error));
      }
    }
  }
  const bar = el('div', '', 'toolbar');
  bar.append(
    q.label,
    sort.label,
    button(
      'Find Events',
      () => {
        page = 1;
        void load();
      },
      false,
      'search',
    ),
  );
  filters.append(bar);
  async function drawStrip() {
    if (!calendarId) {
      timeHost.hidden = true;
      return;
    }
    try {
      // Without a year in the address, the year the calendar is anchored to, as the calendar opens on.
      if (!yearField.input.value) {
        const definition = await client
          .GET('/tenants/{tenant_id}/calendars/{entity_id}', {
            params: { path: { tenant_id: tenantId, entity_id: calendarId } },
          })
          .then((r) => r.data?.definition);
        yearField.input.value = String(
          definition?.week?.reference.year ?? definition?.moons[0]?.reference.year ?? 0,
        );
      }
      const year = Number(yearField.input.value);
      const calculated = await unwrap(
        await client.GET('/tenants/{tenant_id}/calendars/{entity_id}/years/{year}', {
          params: { path: { tenant_id: tenantId, entity_id: calendarId, year } },
        }),
      );
      strip = calculated.segments.map((x) => ({
        key: x.key,
        name: x.name,
        days: x.days.length,
        festival: x.month_ordinal === null,
      }));
      // A tick for every day something is dated on, read from every Event the person can see.
      const everyone = await fetchAllPages(async (n) =>
        unwrap(
          await client.GET('/tenants/{tenant_id}/events', {
            params: { path: { tenant_id: tenantId }, query: { page: n, size: 100 } },
          }),
        ),
      );
      const metas = await Promise.all(everyone.map((e) => metaFor(e.entity_id)));
      const marks: Array<[string, number]> = [];
      for (const m of metas)
        for (const d of m.dates)
          if (d.calendar === calendarId && d.year === year && d.segment && d.day !== null)
            marks.push([d.segment, d.day]);
      const filter = createTimeFilter({
        segments: strip,
        marks,
        initial: range,
        onChange: (next) => {
          range = next;
          page = 1;
          void load();
        },
      });
      const choosers = el('div', '', 'form-grid');
      choosers.append(...(calendars.length > 1 ? [calendarChoice.label] : []), yearField.label);
      timeHost.replaceChildren(filter.element, choosers);
      timeHost.hidden = false;
    } catch (error) {
      timeHost.replaceChildren(el('p', `Could not draw the year. ${message(error)}`, 'caption'));
    }
  }
  const calendars = await fetchAllPages(async (n) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/calendars', {
        params: { path: { tenant_id: tenantId }, query: { page: n, size: 100 } },
      }),
    ),
  ).catch(() => []);
  if (!calendars.some((c) => c.entity_id === calendarId))
    calendarId = calendars[0]?.entity_id ?? '';
  for (const c of calendars) {
    const option = el('option', c.name);
    option.value = c.entity_id;
    calendarChoice.input.append(option);
  }
  calendarChoice.input.value = calendarId;
  for (const input of [calendarChoice.input, yearField.input])
    input.addEventListener('change', () => {
      if (calendarChoice.input.value !== calendarId) yearField.input.value = '';
      calendarId = calendarChoice.input.value;
      range = null;
      page = 1;
      stripReady = drawStrip();
      void load();
    });
  if (canReadEventOrder) {
    const advanced = disclosure(canOrderEvents ? 'Participants and causes' : 'Causes');
    advanced.body.append(
      ...(canOrderEvents
        ? [
            entryPicker(tenantId, 'Filter by being', 'being', (entry) => {
              being = entry.id;
              page = 1;
              showChoices();
              void load();
            }),
          ]
        : []),
      entryPicker(tenantId, 'Follow an Event', 'event', (entry) => {
        chain = entry.id;
        page = 1;
        showChoices();
        void load();
      }),
      direction.label,
      choices,
      button(
        canOrderEvents ? 'Clear participant and causal filters' : 'Clear causal filter',
        () => {
          being = '';
          chain = '';
          page = 1;
          showChoices();
          void load();
        },
        true,
        'close',
      ),
    );
    filters.append(advanced.root);
  }
  if (session.canCreateEntries) {
    const create = disclosure('Create an Event', true);
    create.root.classList.add('event-create');
    const form = el('form', '', 'stack');
    const name = field('Event name');
    name.input.required = true;
    const visibility = creationVisibility();
    const kind = select(
      'Entry kind',
      [
        ['event', 'Event'],
        ['fact', 'Fact'],
      ],
      'event',
    );
    const save = submit('Create Event');
    kind.input.addEventListener('change', () => {
      save.textContent = kind.input.value === 'event' ? 'Create Event' : 'Create Fact';
      visibility.setEvent(kind.input.value === 'event');
    });
    const progress = feedback();
    const id = crypto.randomUUID();
    const actions = el('div', '', 'row');
    actions.append(save);
    form.append(
      name.label,
      kind.label,
      visibility.label,
      el('p', 'Starts undated. Notes have their own audiences.', 'caption'),
      actions,
      progress.node,
    );
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      save.disabled = true;
      progress.busy('Creating…');
      try {
        await unwrap(
          await client.POST('/tenants/{tenant_id}/entities', {
            params: { path: { tenant_id: tenantId } },
            body: {
              id,
              name: name.input.value,
              kinds: [kind.input.value as 'event' | 'fact'],
              visibility: visibility.value(),
              parents: [],
            },
          }),
        );
        if (form.isConnected) location.assign(entryHref(tenantId, id));
      } catch (error) {
        try {
          const existing = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
            params: { path: { tenant_id: tenantId, entity_id: id } },
          });
          if (existing.data?.kinds.includes(kind.input.value as 'event' | 'fact')) {
            if (form.isConnected) location.assign(entryHref(tenantId, id));
            return;
          }
        } catch {
          /* Keep the stable retry identity and draft. */
        }
        progress.fail(`${message(error)} Your draft is kept.`);
        save.disabled = false;
      }
    });
    create.body.append(form);
    host.append(create.root);
    // The page's main action opens the form that makes one.
    const headActions = el('div', '', 'page-heading-actions');
    const open = el('button', '', 'btn btn-primary');
    open.type = 'button';
    open.append(icon('add'), document.createTextNode('New Event'));
    open.addEventListener('click', () => {
      create.root.open = true;
      create.root.scrollIntoView({ block: 'start' });
      name.input.focus();
    });
    headActions.append(open);
    head.querySelector('h1')?.after(headActions);
  }
  host.append(
    timeHost,
    filters,
    el(
      'p',
      canOrderEvents
        ? 'Story order follows recorded relationships. Linearized placements supply no evidence of chronology. Causal filters follow causes, including branches.'
        : 'Your story order uses shared relationships between Events you can see. Linearized placements are display order, not evidence of chronology. Other readers may see a different order.',
      'caption',
    ),
    status.node,
    list,
    nav,
  );
  showChoices();
  stripReady = drawStrip();
  await load();
}
