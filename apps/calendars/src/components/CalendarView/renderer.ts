import { fill } from '@lorenzo/api-client';
import { openMenu } from '@lorenzo/app-shell';
import { renderAudienceControl } from '@lorenzo/information-editor';
import { canonicalAddress, rememberEntryAddress, resolveAddress } from '../../lib/addresses';
import { client, fetchAllPages, unwrap } from '../../lib/api';
import { BRANDING_CSS_URL } from '../../lib/config';
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
} from '../../lib/dom';
import { informationView, renderText } from '../../lib/information';
import { prefetchEntry, prefetchYear } from '../../lib/prefetch';
import { rememberThisPage } from '../../lib/recent';
import { appRegistry } from '../../lib/registry';
import { currentShell, start } from '../../lib/session';
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
    // The calendar and its entry do not wait for each other.
    const [calendar, entry] = await Promise.all([
      client
        .GET('/tenants/{tenant_id}/calendars/{entity_id}', {
          params: { path: { tenant_id: tenantId, entity_id: calendarId } },
        })
        .then(unwrap),
      client
        .GET('/tenants/{tenant_id}/entities/{entity_id}', {
          params: { path: { tenant_id: tenantId, entity_id: calendarId } },
        })
        .then(unwrap),
    ]);
    if (!host?.isConnected) return;
    rememberEntryAddress(tenantId, entry);
    canonicalAddress(tenantId, calendarId);
    rememberThisPage(tenantId, calendar.name);
    // The head (CS6): the calendar's name small over the segment's name large, and on the right the
    // choices that change what is shown (month or whole year, the year, the calendar's own page and,
    // for whoever can write, its definition).
    const head = el('div', '', 'cal-head');
    const titleBlock = el('div', '', 'cal-title');
    const over = el('div', '', 'cal-over');
    const overYear = el('span');
    over.append(el('h1', calendar.name), overYear);
    const bigTitle = el('h2', '', 'cal-big display');
    titleBlock.append(over, bigTitle);
    const controls = el('div', '', 'cal-controls');
    const viewSlot = el('div', '', 'cal-view');
    head.append(titleBlock, controls);
    wait.replaceWith(head);
    let edit: ReturnType<typeof disclosure> | undefined;
    if (canWrite) {
      edit = disclosure('Edit calendar definition', true);
      edit.root.classList.add('cal-edit');
      edit.body.append(
        definitionEditor(tenantId, calendar),
        renderAudienceControl({ client, tenantId, entityId: calendarId }),
      );
    }
    const fallback =
      calendar.definition.week?.reference.year ?? calendar.definition.moons[0]?.reference.year ?? 0;
    let year = params.has('year') ? Number(params.get('year')) : fallback;
    const y = field('Year', String(year), 'number');
    y.input.min = '-1000000';
    y.input.max = '1000000';
    y.label.classList.add('year-field');
    const yearNav = el('form', '', 'year-nav');
    const go = el('button', 'Open year', 'btn btn-secondary');
    go.type = 'submit';
    yearNav.append(
      button('Previous year', () => openYear(year - 1), true, 'previous'),
      y.label,
      button('Next year', () => openYear(year + 1), true, 'next'),
      go,
    );
    const entryLink = linkButton(
      'Calendar entry',
      entryHref(tenantId, calendarId),
      'kind-calendar',
    );
    controls.append(viewSlot, yearNav, entryLink);
    if (edit) {
      const editing = edit;
      const open = button(
        'Edit the calendar',
        () => {
          editing.root.open = !editing.root.open;
          if (editing.root.open) editing.root.scrollIntoView({ block: 'start' });
        },
        true,
        'edit',
      );
      controls.append(open);
      host.append(edit.root);
    }
    const status = feedback();
    host.append(status.node);
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
    // A day's marks (CS5): up to two small symbols and "+N" for the rest, the words of each kept for a
    // reader of the page (and for the panel, which has them in full).
    type Mark = { kind: 'note' | 'entry' | 'observance'; text: string };
    const markIcons = { note: 'kind-fact', entry: 'kind-entity', observance: 'kind-observance' };
    const dayState = new WeakMap<HTMLElement, { items: Mark[]; loading: boolean }>();
    function paintDay(content: HTMLElement) {
      const state = dayState.get(content);
      if (!state) return;
      const nodes: Node[] = [];
      if (state.loading) nodes.push(el('span', 'Loading notes…', 'skeleton day-item day-loading'));
      if (state.items.length) {
        const marks = el('span', '', 'day-marks');
        marks.setAttribute('aria-hidden', 'true');
        for (const item of state.items.slice(0, 2)) {
          const mark = el('span', '', `day-mark day-mark--${item.kind}`);
          mark.title = item.text;
          mark.append(icon(markIcons[item.kind]));
          marks.append(mark);
        }
        if (state.items.length > 2)
          marks.append(el('span', `+${state.items.length - 2}`, 'day-more'));
        nodes.push(marks);
        // What each mark is, in words, for a screen reader and for finding it on the page.
        for (const item of state.items) nodes.push(el('span', item.text, 'visually-hidden'));
      }
      content.replaceChildren(...nodes);
      // How much is written, for the year's squares: darker for more.
      const cell = content.parentElement;
      if (cell) cell.dataset.level = String(Math.min(3, state.items.length));
    }
    function dayItems(content: HTMLElement, change: { items?: Mark[]; loading?: boolean }) {
      const state = dayState.get(content) ?? { items: [], loading: false };
      if (change.items) state.items = [...state.items, ...change.items];
      if (change.loading !== undefined) state.loading = change.loading;
      dayState.set(content, state);
      paintDay(content);
    }
    // The Sessions of the library, read once for the page (CS1: a day lists the Sessions that start on
    // it). What the person may not see is not in the answer, and a failure leaves the day without them.
    let sessionRows:
      | Promise<Array<{ id: string; name: string; start_period_id: string | null }>>
      | undefined;
    const readSessions = () =>
      (sessionRows ??= client
        .GET('/tenants/{tenant_id}/sessions', { params: { path: { tenant_id: tenantId } } })
        .then(unwrap)
        .catch(() => []));
    type DaySummary = { notes: string[]; entries: string[] };
    const contentCache = new Map<string, Promise<DaySummary>>();
    const summaryReads = new Map<string, Promise<void>>();
    // What a saved day shows, in one request for the whole month or festival (ADR 0324) instead
    // of two per day. The notes are the source of each note's first text, drawn here as before so
    // that a link in a note still resolves; hidden notes and entries are not in the answer.
    function loadSummaries(segment: string): Promise<void> {
      const key = `${year}|${segment}`;
      const known = summaryReads.get(key);
      if (known) return known;
      const reading = (async () => {
        const items = await fetchAllPages(async (page) =>
          unwrap(
            await client.GET(
              '/tenants/{tenant_id}/calendars/{calendar_id}/years/{year}/period-summaries',
              {
                params: {
                  path: { tenant_id: tenantId, calendar_id: calendarId, year },
                  query: { segment, page, size: 100 },
                },
              },
            ),
          ),
        );
        for (const item of items) {
          contentCache.set(
            item.entity_id,
            (async (): Promise<DaySummary> => {
              const notes = await Promise.all(
                item.notes.map(async (note) => {
                  const parsed = note.text
                    ? (new DOMParser().parseFromString(
                        await renderText(tenantId, note.text),
                        'text/html',
                      ).body.textContent ?? '')
                    : '';
                  const title = note.title && note.title !== 'Imported note' ? note.title : '';
                  const summary = [title, parsed.trim()]
                    .filter(Boolean)
                    .join(' · ')
                    .replace(/\s+/g, ' ');
                  return summary
                    ? summary.slice(0, 180) + (summary.length > 180 || note.truncated ? '…' : '')
                    : 'Note';
                }),
              );
              return { notes, entries: item.entries.map((e) => e.name) };
            })(),
          );
        }
      })();
      summaryReads.set(key, reading);
      void reading.catch(() => {
        if (summaryReads.get(key) === reading) summaryReads.delete(key);
      });
      return reading;
    }
    function loadDays(segment: string, jobs: Array<{ period: Period; content: HTMLElement }>) {
      void loadSummaries(segment)
        .then(async () => {
          for (const { period, content } of jobs) {
            if (!content.isConnected) continue;
            const summary = await contentCache.get(period.entity_id);
            if (!content.isConnected) continue;
            dayItems(content, {
              loading: false,
              items: [
                ...(summary?.notes ?? []).map(
                  (note): Mark => ({ kind: 'note', text: `Note · ${note}` }),
                ),
                ...(summary?.entries ?? []).map((name): Mark => ({ kind: 'entry', text: name })),
              ],
            });
          }
        })
        .catch(() => {
          for (const { content } of jobs) {
            if (content.isConnected) {
              dayState.set(content, { items: [], loading: false });
              content.replaceChildren(
                el('span', 'Could not load notes and entries.', 'day-item error-text'),
              );
            }
          }
        });
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
      summaryReads.clear();
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
      const tabs = el('div', '', 'tabs view-switch');
      tabs.setAttribute('role', 'tablist');
      tabs.setAttribute('aria-label', 'Calendar view');
      const monthPanel = el('div', '', 'stack');
      const yearPanel = el('div', '', 'stack year-segments');
      const panels = [monthPanel, yearPanel];
      const tabButtons = ['Month', 'Whole year'].map((name, index) => {
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
      viewSlot.replaceChildren(tabs);
      const notesRow = el('div', '', 'cal-notes-row');
      notesRow.append(
        button(
          `Year ${year}: notes and dated entries`,
          () => showPeriod(undefined, undefined, undefined, true),
          true,
          'kind-calendar-pin',
        ),
      );
      grid.append(notesRow, monthPanel, yearPanel);
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
            showSegment(segment.key, month, true);
          }
          yearPanel.append(
            el(
              'p',
              'Each square is a day. Darker means more is written on it. Choose a day to read it in the panel.',
              'year-note',
            ),
          );
        } else {
          if (!preview.segments.some((s) => s.key === chosenSegment))
            chosenSegment = preview.segments[0]?.key ?? '';
          const strip = el('div', '', 'seg-strip horizontal-mask');
          strip.setAttribute('role', 'group');
          strip.setAttribute('aria-label', 'Month or festival');
          const days = el('div', '', 'stack');
          monthPanel.append(strip, days);
          const chips = new Map<string, HTMLButtonElement>();
          const choose = (key: string) => {
            chosenSegment = key;
            for (const [chipKey, chip] of chips)
              chip.setAttribute('aria-pressed', String(chipKey === key));
            chips.get(key)?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
            showSegment(key, days, false);
            setTitle();
          };
          for (const definition of calendar.definition.segments) {
            const shown = preview.segments.find((s) => s.key === definition.key);
            if (!shown) {
              // A leap segment that this year does not have keeps its place, and cannot be opened.
              const absent = el('div', '', 'seg-chip seg-chip--absent');
              absent.append(
                el('span', definition.name, 'seg-name'),
                el('span', 'absent this year', 'seg-meta'),
              );
              strip.append(absent);
              continue;
            }
            const chip = el('button', '', `seg-chip${shown.kind === 'festival' ? ' fest' : ''}`);
            chip.type = 'button';
            chip.dataset.segment = shown.key;
            // How much is written: a dot for each fifth of the days that have something.
            const written = periods.filter((p) => p.segment === shown.key && p.day !== null).length;
            const filled =
              written === 0 ? 0 : Math.max(1, Math.ceil((written / shown.days.length) * 5));
            const dots = el('span', '', 'seg-density');
            dots.setAttribute('aria-hidden', 'true');
            for (let i = 0; i < 5; i++) dots.append(el('span', '', i < filled ? 'on' : ''));
            chip.append(
              el('span', shown.name, 'seg-name'),
              el(
                'span',
                `${shown.days.length} ${shown.days.length === 1 ? 'day' : 'days'}`,
                'seg-meta',
              ),
              dots,
            );
            chip.setAttribute('aria-pressed', String(shown.key === chosenSegment));
            chip.addEventListener('click', () => choose(shown.key));
            chips.set(shown.key, chip);
            strip.append(chip);
          }
          // Page Up and Page Down change segment, from the strip or the grid.
          monthPanel.addEventListener('keydown', (event) => {
            if (event.key !== 'PageUp' && event.key !== 'PageDown') return;
            const keys = [...chips.keys()];
            const next = keys.indexOf(chosenSegment) + (event.key === 'PageDown' ? 1 : -1);
            if (next < 0 || next >= keys.length) return;
            event.preventDefault();
            const target = keys[next] ?? chosenSegment;
            choose(target);
            chips.get(target)?.focus();
          });
          showSegment(chosenSegment, days, false);
          // The strip opens with the segment on show in view, however far along it is.
          chips.get(chosenSegment)?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
        }
        setTitle();
      }
      activate(wholeYear ? 1 : 0);
    }
    // The heading that says which segment is shown: the head of the page for the month, and a row's
    // name in the whole year.
    function setTitle() {
      overYear.textContent = `· Year ${year}`;
      bigTitle.textContent = wholeYear
        ? `Year ${year}`
        : (preview.segments.find((s) => s.key === chosenSegment)?.name ?? '');
    }
    function showSegment(key: string, container: HTMLElement, inYear: boolean) {
      const segment = preview.segments.find((s) => s.key === key);
      if (!segment) return;
      container.replaceChildren();
      const notes = button(
        'Month or festival notes',
        () => showPeriod(key, undefined, notes),
        true,
        'kind-calendar-pin',
      );
      if (inYear) {
        // A row of the year: the segment's name and size on the left, its days as squares.
        const head = el('div', '', 'year-head');
        // In a row of the year it is a quiet "Notes", still named for what it opens.
        notes.classList.replace('btn-secondary', 'btn-text');
        notes.setAttribute('aria-label', 'Month or festival notes');
        if (notes.lastChild) notes.lastChild.textContent = 'Notes';
        head.append(
          el('h2', segment.name),
          el(
            'p',
            `${segment.days.length} ${segment.days.length === 1 ? 'day' : 'days'}`,
            'caption',
          ),
          notes,
        );
        container.append(head);
      } else {
        const row = el('div', '', 'cal-notes-row');
        row.append(notes);
        container.append(row);
      }
      const definition = calendar.definition.segments.find((s) => s.key === key);
      const week = calendar.definition.week;
      const useWeek = Boolean(week && definition?.in_week);
      const cells = el(
        'div',
        '',
        inYear ? `year-days${useWeek ? '' : ' festival'}` : useWeek ? 'month-grid' : 'festival',
      );
      cells.style.setProperty('--week-length', String(week?.length ?? 7));
      if (useWeek && !inYear) {
        cells.tabIndex = 0;
        cells.setAttribute('role', 'group');
        cells.setAttribute('aria-label', `Dates in ${segment.name} ${year}`);
      }
      if (useWeek && week && !inYear) {
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
        const cell = el('div', '', inYear ? 'day day--square' : 'day');
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
        // In the year a day is a square with no words on it; its name is the button's.
        if (!inYear) press.append(header);
        const content = el('div', '', 'day-content');
        cell.append(press, content);
        const saved = periods.find((p) => p.segment === key && p.day === day.date.day);
        if (saved) {
          press.addEventListener('pointerenter', () => prefetchEntry(tenantId, saved.entity_id));
          press.addEventListener('focus', () => prefetchEntry(tenantId, saved.entity_id));
          dayItems(content, { loading: true });
          pending.push({ period: saved, content });
        }
        const recurring = occurrences
          .filter((o) => o.date.segment === key && o.date.day === day.date.day)
          .map((o): Mark => ({ kind: 'observance', text: `Recurring · ${o.name}` }));
        if (recurring.length) dayItems(content, { items: recurring });
        cells.append(cell);
      }
      container.append(cells);
      if (!inYear)
        // The arrow keys move through the days: along the week, and down and up a week.
        cells.addEventListener('keydown', (event) => {
          const buttons = [...cells.querySelectorAll<HTMLButtonElement>('.day-button')];
          const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
          const weekLength = useWeek ? (week?.length ?? 7) : 0;
          const step = {
            ArrowLeft: -1,
            ArrowRight: 1,
            ArrowUp: -weekLength,
            ArrowDown: weekLength,
          }[event.key];
          if (at < 0 || !step) return;
          const target = buttons[at + step];
          if (!target) return;
          event.preventDefault();
          target.focus();
        });
      if (pending.length) loadDays(key, pending);
    }
    async function showPeriod(
      segment?: string,
      day?: number,
      target?: HTMLButtonElement,
      forceOpen = false,
    ) {
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
      detail.replaceChildren();
      // On a narrow window the panel is a sheet (CS6): it is there once a date, or the year's notes,
      // has been chosen, and goes with Close; beside the grid it is always there.
      if (segment !== undefined || forceOpen) detail.dataset.open = '';
      const close = button(
        'Close',
        () => {
          delete detail.dataset.open;
          grid
            .querySelector<HTMLElement>('.day-button[aria-pressed="true"]')
            ?.focus({ preventScroll: true });
        },
        true,
        'close',
      );
      close.classList.add('sheet-close');
      detail.append(close);
      if (segment && day !== undefined) {
        // Which day of the week and of the year it is, over its name.
        const shown = preview.segments.find((s) => s.key === segment);
        const index = shown?.days.findIndex((d) => d.date.day === day) ?? -1;
        const before = preview.segments
          .slice(
            0,
            preview.segments.findIndex((s) => s.key === segment),
          )
          .reduce((total, s) => total + s.days.length, 0);
        const weekday = shown?.days[index]?.weekday;
        const weekdayName =
          weekday === null || weekday === undefined
            ? ''
            : (calendar.definition.week?.names?.[weekday] ?? '');
        if (index >= 0)
          detail.append(
            el(
              'p',
              `${weekdayName ? `${weekdayName} · ` : ''}day ${before + index + 1} of Year ${year}`,
              'caption day-over',
            ),
          );
      }
      detail.append(el('h2', title));
      const addSlot = el('div', '', 'day-add');
      detail.append(addSlot);
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
      // The status bar says which date is on show and whether anything is written on it (screen 01).
      currentShell()?.statusBar({
        meta: `${title} · ${saved ? 'period written' : 'nothing written'}`,
      });
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
        if (saved) {
          const template = (await appRegistry())?.links.session;
          const starting = template
            ? (await readSessions()).filter((row) => row.start_period_id === saved.entity_id)
            : [];
          if (turn !== selection || !host?.isConnected) return;
          if (template && starting.length) {
            const block = el('section', '', 'stack-tight day-sessions');
            const sessions = el('ul', '', 'list');
            for (const row of starting) {
              const item = el('li', '', 'row');
              const open = el('a', row.name);
              open.href = fill(template, { tenant: tenantId, id: row.id });
              item.append(icon('kind-session'), open, el('span', 'Starts here', 'caption'));
              sessions.append(item);
            }
            block.append(el('h3', 'Sessions'), sessions);
            detail.append(block);
          }
        }
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
          const create = disclosure('Create a fact or story event');
          create.body.append(createDatedEntry(tenantId, materialize));
          const existing = disclosure('Associate an existing fact or event');
          existing.body.append(attachExisting(tenantId, materialize));
          const recurring =
            segment && day !== undefined ? disclosure('Create a recurring observance') : undefined;
          if (recurring && segment && day !== undefined)
            recurring.body.append(
              createObservance(tenantId, calendarId, calendar.definition, {
                segment,
                day,
                when: { every: 1, offset: 0 },
              }),
            );
          // The forms are not on the panel until "Add to this day" asks for one.
          const forms = [create, existing, recurring].filter(
            (form): form is NonNullable<typeof form> => form !== undefined,
          );
          for (const form of forms) form.root.classList.add('add-form');
          const reveal = (form: (typeof forms)[number]) => {
            for (const other of forms) other.root.open = other === form;
            form.root.scrollIntoView?.({ block: 'nearest' });
            form.body.querySelector<HTMLElement>('input, select, textarea')?.focus();
          };
          const chooseKind = (kind: 'event' | 'fact') => {
            const kinds = create.body.querySelector<HTMLSelectElement>('select');
            if (!kinds) return;
            kinds.value = kind;
            kinds.dispatchEvent(new Event('change'));
          };
          const addNote = async () => {
            try {
              const period = await materialize();
              if (!host?.isConnected) return;
              location.assign(
                `${entryHref(tenantId, period.entity_id)}&calendar=${encodeURIComponent(calendarId)}&year=${chosenYear}&add=information`,
              );
            } catch (e) {
              localStatus.fail(message(e));
            }
          };
          const add = button(
            'Add to this day',
            () => {
              openMenu(
                add,
                [
                  { label: 'A note on this day', icon: 'kind-fact', run: () => void addNote() },
                  {
                    label: 'An Event',
                    icon: 'kind-event',
                    run: () => {
                      chooseKind('event');
                      reveal(create);
                    },
                  },
                  {
                    label: 'A Fact',
                    icon: 'kind-fact',
                    run: () => {
                      chooseKind('fact');
                      reveal(create);
                    },
                  },
                  {
                    label: 'An existing Event or Fact…',
                    icon: 'link',
                    run: () => reveal(existing),
                  },
                  ...(recurring
                    ? [
                        { separator: true as const },
                        {
                          label: 'A recurring observance…',
                          icon: 'kind-observance',
                          run: () => reveal(recurring),
                        },
                      ]
                    : []),
                ],
                { label: 'Add to this day', sprite: `${BRANDING_CSS_URL}/icons.svg` },
              );
            },
            true,
            'add',
          );
          add.setAttribute('aria-haspopup', 'menu');
          addSlot.append(add);
          detail.append(...forms.map((form) => form.root));
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
