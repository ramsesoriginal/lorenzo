import { renderAudienceControl } from '@lorenzo/information-editor';
import { canonicalAddress, rememberEntryAddress, resolveAddress } from '../../lib/addresses';
import { client, fetchAllPages, unwrap } from '../../lib/api';
import {
  attachExisting,
  createDatedEntry,
  createObservance,
  datedEntries,
} from '../../lib/dated-entries';
import { definitionEditor } from '../../lib/definition-editor';
import {
  button,
  disclosure,
  el,
  entryHref,
  failure,
  feedback,
  field,
  icon,
  iconLink,
  link,
  linkButton,
  loading,
  message,
  select,
} from '../../lib/dom';
import { informationView, renderText } from '../../lib/information';
import { prefetchEntry, prefetchYear } from '../../lib/prefetch';
import { start } from '../../lib/session';
import type { Period, YearPreview } from '../../lib/types';

// Phase n of the calendar engine's int(fraction * 8): the words, and the atlas symbol (ADR 0326).
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
const phaseIcons = [
  'moon-new',
  'moon-waxing-crescent',
  'moon-first-quarter',
  'moon-waxing-gibbous',
  'moon-full',
  'moon-waning-gibbous',
  'moon-last-quarter',
  'moon-waning-crescent',
];
const moonIcon = (phase: number) => icon(phaseIcons[phase] ?? 'moon-new');

export async function mount() {
  const host = document.querySelector<HTMLElement>('#CalendarView');
  if (!host || host.dataset.mounted) return;
  host.dataset.mounted = 'true';
  const session = await start();
  if (!session || !host?.isConnected) return;
  const { tenantId, canWrite } = session;
  const params = new URLSearchParams(location.search);
  const wait = loading('Opening calendar…');
  host.append(iconLink('All calendars', `/?tenant=${encodeURIComponent(tenantId)}`, 'back'), wait);
  try {
    const calendarId = await resolveAddress(tenantId, params, 'calendar');
    const calendar = await unwrap(
      await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
        params: { path: { tenant_id: tenantId, entity_id: calendarId } },
      }),
    );
    const entry = await unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenantId, entity_id: calendarId } },
      }),
    );
    if (!host?.isConnected) return;
    rememberEntryAddress(tenantId, entry);
    canonicalAddress(tenantId, calendarId);
    const head = el('div', '', 'page-header');
    head.append(
      el('h1', calendar.name),
      linkButton('Calendar entry', entryHref(tenantId, calendarId), 'kind-calendar'),
    );
    wait.replaceWith(head);
    if (canWrite) {
      const edit = disclosure('Edit calendar definition', true);
      edit.body.append(
        definitionEditor(tenantId, calendar),
        renderAudienceControl({ client, tenantId, entityId: calendarId }),
      );
      host.append(edit.root);
    }
    const fallback =
      calendar.definition.week?.reference.year ?? calendar.definition.moons[0]?.reference.year ?? 0;
    let year = params.has('year') ? Number(params.get('year')) : fallback;
    const y = field('Year', String(year), 'number');
    y.input.min = '-1000000';
    y.input.max = '1000000';
    y.label.classList.add('year-field');
    const yearNav = el('form', '', 'toolbar year-nav');
    const go = el('button', 'Open year', 'btn btn-secondary');
    go.type = 'submit';
    yearNav.append(
      button('Previous year', () => openYear(year - 1), true, 'previous'),
      y.label,
      button('Next year', () => openYear(year + 1), true, 'next'),
      go,
    );
    const status = feedback();
    host.append(yearNav, status.node);
    const body = el('div', '', 'calendar-layout');
    const grid = el('section', '', 'stack');
    const detail = el('aside', '', 'card card-body stack');
    detail.setAttribute('aria-live', 'polite');
    body.append(grid, detail);
    host.append(body);
    let wholeYear = params.get('view') === 'year';
    let chosenSegment = params.get('segment') ?? '';
    let requestedDate = params.has('segment');
    let requestedDay = params.has('day') ? Number(params.get('day')) : null;
    let preview: YearPreview;
    let periods: Period[] = [];
    let occurrences: Array<{
      entity_id: string;
      name: string;
      date: { year: number; segment: string; day: number };
    }> = [];
    const contentCache = new Map<string, Promise<{ notes: string[]; entries: string[] }>>();
    async function dayContent(periodId: string) {
      const known = contentCache.get(periodId);
      if (known) return known;
      const loading = (async () => {
        const [notes, entries] = await Promise.all([
          fetchAllPages(async (page) =>
            unwrap(
              await client.GET('/tenants/{tenant_id}/entities/{entity_id}/information', {
                params: {
                  path: { tenant_id: tenantId, entity_id: periodId },
                  query: { page, size: 100 },
                },
              }),
            ),
          ),
          fetchAllPages(async (page) =>
            unwrap(
              await client.GET('/tenants/{tenant_id}/calendar-periods/{period_id}/entries', {
                params: {
                  path: { tenant_id: tenantId, period_id: periodId },
                  query: { page, size: 100 },
                },
              }),
            ),
          ),
        ]);
        const summaries = await Promise.all(
          notes.map(async (note) => {
            const text = note.payloads.find((p) => p.kind === 'description');
            const parsed =
              text?.kind === 'description'
                ? (new DOMParser().parseFromString(
                    await renderText(tenantId, text.content),
                    'text/html',
                  ).body.textContent ?? '')
                : '';
            const title = note.title && note.title !== 'Imported note' ? note.title : '';
            const summary = [title, parsed.trim()].filter(Boolean).join(' · ').replace(/\s+/g, ' ');
            return summary ? summary.slice(0, 180) + (summary.length > 180 ? '…' : '') : 'Note';
          }),
        );
        return { notes: summaries, entries: entries.map((e) => e.name) };
      })();
      contentCache.set(periodId, loading);
      void loading.catch(() => {
        if (contentCache.get(periodId) === loading) contentCache.delete(periodId);
      });
      return loading;
    }
    const dayQueue: Array<{ period: Period; content: HTMLElement }> = [];
    let activeDays = 0;
    function loadDays() {
      while (activeDays < 4 && dayQueue.length) {
        const job = dayQueue.shift();
        if (!job?.content.isConnected) continue;
        activeDays++;
        const { period, content } = job;
        void (async () => {
          try {
            const summary = await dayContent(period.entity_id);
            if (!content.isConnected) return;
            content.replaceChildren(
              ...summary.notes.map((note) => el('span', `Note · ${note}`, 'day-item day-note')),
              ...summary.entries.map((name) => el('span', name, 'day-item day-entry')),
            );
          } catch {
            if (content.isConnected)
              content.replaceChildren(
                el('span', 'Could not load notes and entries.', 'day-item error-text'),
              );
          }
        })().finally(() => {
          activeDays--;
          loadDays();
        });
      }
    }
    let generation = 0;
    let selection = 0;
    // The day the panel is about, shown pressed in the grid.
    let selectedDay: { segment: string; day: number } | null = null;
    yearNav.addEventListener('submit', (event) => {
      event.preventDefault();
      void openYear(Number(y.input.value));
    });
    async function openYear(next: number) {
      if (!Number.isInteger(next) || Math.abs(next) > 1000000) {
        status.fail('Enter a whole year between −1000000 and 1000000.');
        return;
      }
      const turn = ++generation;
      const selectRequested = requestedDate;
      const dayRequested = requestedDay;
      requestedDate = false;
      requestedDay = null;
      contentCache.clear();
      status.busy('Opening year…');
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
        if (turn !== generation || !host?.isConnected) return;
        year = next;
        y.input.value = String(year);
        preview = calculated;
        periods = saved;
        for (const period of saved) rememberEntryAddress(tenantId, period);
        occurrences = observances;
        status.clear();
        const url = new URL(location.href);
        url.searchParams.set('year', String(year));
        history.replaceState(history.state, '', url);
        showYear();
        const target = preview.segments.find((s) => s.key === chosenSegment);
        if (
          selectRequested &&
          target &&
          (dayRequested === null || target.days.some((d) => d.date.day === dayRequested))
        ) {
          await showPeriod(target.key, dayRequested ?? undefined);
        } else await showPeriod();
        requestedDay = null;
        requestedDate = false;
        if (
          calendar.definition.segments.reduce((total, s) => total + s.days, 0) <= 1000 &&
          calendar.definition.moons.length <= 8
        )
          prefetchYear(tenantId, calendarId, year + 1);
      } catch (e) {
        if (turn === generation) status.fail(message(e));
      }
    }
    function showYear() {
      grid.replaceChildren();
      const tabs = el('div', '', 'tabs');
      tabs.setAttribute('role', 'tablist');
      tabs.setAttribute('aria-label', 'Calendar view');
      const monthPanel = el('div', '', 'stack');
      const yearPanel = el('div', '', 'stack year-segments');
      const panels = [monthPanel, yearPanel];
      const tabButtons = ['Month or festival', 'Whole year'].map((name, index) => {
        const tab = button(name, () => activate(index), true);
        tab.className = 'tab';
        tab.id = `calendar-view-tab-${index}`;
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', `calendar-view-panel-${index}`);
        const panel = panels[index];
        panel.id = `calendar-view-panel-${index}`;
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', tab.id);
        panel.tabIndex = 0;
        tab.addEventListener('keydown', (event) => {
          let next: number;
          switch (event.key) {
            case 'ArrowLeft':
            case 'ArrowRight':
              next = 1 - index;
              break;
            case 'Home':
              next = 0;
              break;
            case 'End':
              next = 1;
              break;
            default:
              return;
          }
          event.preventDefault();
          activate(next);
          tabButtons[next].focus();
        });
        tabs.append(tab);
        return tab;
      });
      const bar = el('div', '', 'view-bar');
      bar.append(
        tabs,
        button(
          `Year ${year}: notes and dated entries`,
          () => showPeriod(),
          true,
          'kind-calendar-pin',
        ),
      );
      grid.append(bar, monthPanel, yearPanel);
      function activate(index: number) {
        wholeYear = index === 1;
        detail.querySelector('[data-calendar-return]')?.remove();
        body.classList.toggle('whole-year', wholeYear);
        tabButtons.forEach((tab, i) => {
          tab.setAttribute('aria-selected', String(i === index));
          tab.tabIndex = i === index ? 0 : -1;
          panels[i].hidden = i !== index;
          panels[i].replaceChildren();
        });
        const url = new URL(location.href);
        if (wholeYear) url.searchParams.set('view', 'year');
        else url.searchParams.delete('view');
        history.replaceState(history.state, '', url);
        if (wholeYear) {
          for (const segment of preview.segments) {
            const month = el('section', '', 'stack year-segment');
            yearPanel.append(month);
            showSegment(segment.key, month);
          }
        } else {
          if (!preview.segments.some((s) => s.key === chosenSegment))
            chosenSegment = preview.segments[0]?.key ?? '';
          const picker = select(
            'Month or festival',
            preview.segments.map((s) => [
              s.key,
              `${s.name}${s.kind === 'festival' ? ' · festival' : ''}`,
            ]),
            chosenSegment,
          );
          picker.label.classList.add('narrow-field');
          const days = el('div', '', 'stack');
          monthPanel.append(picker.label, days);
          picker.input.addEventListener('change', () => {
            chosenSegment = picker.input.value;
            showSegment(chosenSegment, days);
          });
          showSegment(chosenSegment, days);
        }
      }
      activate(wholeYear ? 1 : 0);
    }
    function showSegment(key: string, container: HTMLElement) {
      const segment = preview.segments.find((s) => s.key === key);
      if (!segment) return;
      container.replaceChildren();
      const notes = button(
        'Month or festival notes',
        () => showPeriod(key, undefined, notes),
        true,
        'kind-calendar-pin',
      );
      const title = el('div', '', 'section-head');
      title.append(el('h2', segment.name), notes);
      container.append(title);
      const definition = calendar.definition.segments.find((s) => s.key === key);
      const week = calendar.definition.week;
      const useWeek = Boolean(week && definition?.in_week);
      const cells = el('div', '', useWeek ? 'month-grid' : 'festival');
      cells.style.setProperty('--week-length', String(week?.length ?? 7));
      if (useWeek) {
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
      const pending: Array<{ period: Period; content: HTMLElement }> = [];
      for (const day of segment.days) {
        // A cell is the date's button, which carries its name and its moons, and beneath it what
        // is written for the day. The button's own text is only the date, so its name holds it.
        const cell = el('div', '', 'day');
        const press = el('button', '', 'day-button');
        press.type = 'button';
        press.addEventListener('click', () => {
          void showPeriod(key, day.date.day, press);
        });
        press.setAttribute('aria-label', `${day.date.day} ${segment.name} ${year}`);
        press.dataset.day = String(day.date.day);
        press.dataset.segment = key;
        if (selectedDay && selectedDay.segment === key && selectedDay.day === day.date.day)
          press.setAttribute('aria-pressed', 'true');
        const header = el('span', '', 'day-header');
        header.append(el('span', String(day.date.day), 'day-number'));
        const moons = el('span', '', 'moon-phases');
        const moonLabels: string[] = [];
        for (const moon of calendar.definition.moons) {
          const phase = day.moons[moon.key];
          if (phase !== undefined) {
            const label = `${moon.name}: ${phases[phase] ?? phase}`;
            // The symbol is decorative; the words are in the day's description and its panel.
            const mark = el('span', '', 'moon-phase');
            mark.title = label;
            mark.append(moonIcon(phase));
            moons.append(mark);
            moonLabels.push(label);
          }
        }
        if (moonLabels.length) {
          header.append(moons);
          press.setAttribute('aria-description', moonLabels.join('; '));
        }
        press.append(header);
        const content = el('div', '', 'day-content');
        cell.append(press, content);
        const saved = periods.find((p) => p.segment === key && p.day === day.date.day);
        if (saved) {
          press.addEventListener('pointerenter', () => prefetchEntry(tenantId, saved.entity_id));
          press.addEventListener('focus', () => prefetchEntry(tenantId, saved.entity_id));
          content.append(el('span', 'Loading notes…', 'skeleton day-item day-loading'));
          pending.push({ period: saved, content });
        }
        for (const occurrence of occurrences.filter(
          (o) => o.date.segment === key && o.date.day === day.date.day,
        ))
          cell.append(el('span', `Recurring · ${occurrence.name}`, 'day-item day-observance'));
        cells.append(cell);
      }
      container.append(cells);
      dayQueue.push(...pending);
      loadDays();
    }
    async function showPeriod(segment?: string, day?: number, target?: HTMLButtonElement) {
      const turn = ++selection;
      const chosenYear = year;
      const address = new URL(location.href);
      if (segment) address.searchParams.set('segment', segment);
      else address.searchParams.delete('segment');
      if (day !== undefined) address.searchParams.set('day', String(day));
      else address.searchParams.delete('day');
      history.replaceState(history.state, '', address);
      const title = segment
        ? `${day === undefined ? '' : `${day} `}${calendar.definition.segments.find((s) => s.key === segment)?.name ?? segment} ${year}`
        : `Year ${year}`;
      detail.replaceChildren(el('h2', title));
      selectedDay = segment && day !== undefined ? { segment, day } : null;
      for (const pressed of grid.querySelectorAll('.day-button[aria-pressed]'))
        pressed.removeAttribute('aria-pressed');
      if (selectedDay)
        grid
          .querySelector(
            `.day-button[data-segment="${CSS.escape(segment ?? '')}"][data-day="${day}"]`,
          )
          ?.setAttribute('aria-pressed', 'true');
      if (segment && day !== undefined) {
        const reading = preview.segments
          .find((s) => s.key === segment)
          ?.days.find((d) => d.date.day === day);
        const moons = el('ul', '', 'selected-moons');
        for (const moon of calendar.definition.moons) {
          const phase = reading?.moons[moon.key];
          if (phase !== undefined) {
            const item = el('li', '', 'row-tight');
            item.append(
              moonIcon(phase),
              document.createTextNode(`${moon.name}: ${phases[phase] ?? phase}`),
            );
            moons.append(item);
          }
        }
        if (moons.childElementCount) detail.append(moons);
      }
      const saved = periods.find((p) => p.segment === (segment ?? null) && p.day === (day ?? null));
      const localStatus = feedback();
      let materialized = saved;
      const waiting = loading('Opening notes…');
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
          detail.append(waiting);
          const entry = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: { tenant_id: tenantId, entity_id: saved.entity_id } },
            }),
          );
          rememberEntryAddress(tenantId, entry);
          const dates = await datedEntries(tenantId, saved.entity_id);
          if (turn !== selection || !host?.isConnected) return;
          waiting.remove();
          detail.append(
            linkButton(
              'Open date entry',
              `${entryHref(tenantId, saved.entity_id)}&calendar=${encodeURIComponent(calendarId)}&year=${chosenYear}`,
              'next',
            ),
            informationView(tenantId, entry, false, () => {}, false, undefined, true),
            dates,
          );
        } else
          detail.append(
            el('p', 'Nothing is written for this date yet, or none of it is open to you.', 'lede'),
          );
        if (turn !== selection || !host?.isConnected) return;
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
              'Add a note to this date',
              async () => {
                try {
                  const period = await materialize();
                  if (!host?.isConnected) return;
                  location.assign(
                    `${entryHref(tenantId, period.entity_id)}&calendar=${encodeURIComponent(calendarId)}&year=${chosenYear}&add=information`,
                  );
                } catch (e) {
                  localStatus.fail(message(e));
                }
              },
              true,
              'add',
            ),
          );
          const create = disclosure('Create a fact or story event');
          create.body.append(createDatedEntry(tenantId, materialize));
          const existing = disclosure('Associate an existing fact or event');
          existing.body.append(attachExisting(tenantId, materialize));
          detail.append(create.root, existing.root);
          if (segment && day !== undefined) {
            const recurring = disclosure('Create a recurring observance');
            recurring.body.append(
              createObservance(tenantId, calendarId, calendar.definition, {
                segment,
                day,
                when: { every: 1, offset: 0 },
              }),
            );
            detail.append(recurring.root);
          }
        }
        detail.append(localStatus.node);
        if (wholeYear && target?.isConnected && window.matchMedia('(max-width: 720px)').matches) {
          const back = button(
            'Back to calendar',
            () => {
              target.scrollIntoView({ block: 'center' });
              target.focus({ preventScroll: true });
            },
            true,
            'back',
          );
          back.dataset.calendarReturn = '';
          detail.prepend(back);
          detail.scrollIntoView({ block: 'start' });
          back.focus({ preventScroll: true });
        }
      } catch (e) {
        waiting.remove();
        if (turn === selection) localStatus.fail(message(e));
        detail.append(localStatus.node);
      }
    }
    await openYear(year);
  } catch (e) {
    const problem = failure(message(e));
    if (wait.isConnected) wait.replaceWith(problem);
    else host.append(problem);
  }
}
