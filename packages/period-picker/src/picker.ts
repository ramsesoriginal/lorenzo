import { LorenzoApiError, type LorenzoClient } from '@lorenzo/api-client';
import {
  type CalendarChoice,
  loadCalendars,
  loadPeriods,
  loadYear,
  materializeSelection,
  referenceYear,
  savedKey,
  type YearView,
} from './api';
import {
  addAll,
  type Coordinate,
  daysBetween,
  isSelected,
  limit,
  MAX_SELECTION,
  type Mode,
  type Picked,
  periodLabel,
  remove,
  summarize,
  toggle,
} from './model';

export type PeriodPickerOptions = {
  client: LorenzoClient;
  tenantId: string;
  /** One period (a start, a scene's date) or several (the game time a Session covers). */
  mode: Mode;
  /**
   * Whether the person may write to calendars. A day nobody has saved yet can only be chosen by
   * someone who may: saving it creates it.
   */
  canCreate: boolean;
  /** Periods already chosen, by id. */
  initial?: readonly string[];
  /** A label for the control, for the group the picker sits in. */
  label?: string;
  onChange?(selection: readonly Picked[]): void;
};

export type PeriodPicker = {
  element: HTMLElement;
  /** Resolves once the calendars and the initial choice have loaded. */
  ready: Promise<void>;
  selection(): readonly Picked[];
  setSelection(selection: readonly Picked[]): void;
  /** The chosen periods' ids, creating those that do not exist yet. */
  resolve(): Promise<string[]>;
};

type Tag = keyof HTMLElementTagNameMap;

function el<T extends Tag>(
  tag: T,
  className = '',
  text = '',
  attributes: Record<string, string> = {},
): HTMLElementTagNameMap[T] {
  const node = document.createElement(tag);

  if (className) node.className = className;
  if (text) node.textContent = text;

  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);

  return node;
}

function failure(error: unknown): string {
  return error instanceof LorenzoApiError || error instanceof Error
    ? error.message
    : 'Something went wrong.';
}

// The names the API gives a period are "<calendar> <year>", "<month> <year>" and "<day> <month>
// <year>"; a chosen period that was read by id has only its name, so the month's is taken back out.
function segmentNameOf(name: string, hasDay: boolean): string {
  const withoutYear = name.replace(/ -?\d+$/, '');

  return hasDay ? withoutYear.replace(/^\d+ /, '') : withoutYear;
}

let sequence = 0;

export function createPeriodPicker(options: PeriodPickerOptions): PeriodPicker {
  const { client, tenantId, mode, canCreate } = options;
  const id = `period-picker-${++sequence}`;

  let calendars: CalendarChoice[] = [];
  let calendarId = '';
  let year = 0;
  let segmentKey = '';
  let view: YearView | undefined;
  let chosen: Picked[] = [];
  let anchor: { segment: string; day: number } | undefined;
  let ranging = false;
  let loading = true;
  let problem = '';
  // A newer request for a year makes an older answer for another one stale.
  let generation = 0;

  const root = el('div', 'period-picker stack-tight', '', { role: 'group' });
  root.setAttribute('aria-label', options.label ?? 'Choose a date');

  const calendarField = el('label', 'field');
  calendarField.append(el('span', 'field-label', 'Calendar'));
  const calendarSelect = el('select', 'text-input', '', { id: `${id}-calendar` });
  calendarField.append(calendarSelect);

  const yearField = el('label', 'field');
  yearField.append(el('span', 'field-label', 'Year'));
  const yearInput = el('input', 'text-input period-year', '', {
    type: 'number',
    step: '1',
    min: '-1000000',
    max: '1000000',
    inputmode: 'numeric',
  });
  yearField.append(yearInput);
  const previous = el('button', 'btn btn-secondary', 'Previous year', { type: 'button' });
  const next = el('button', 'btn btn-secondary', 'Next year', { type: 'button' });
  const segmentField = el('label', 'field');
  segmentField.append(el('span', 'field-label', 'Month or festival'));
  const segmentSelect = el('select', 'text-input');
  segmentField.append(segmentSelect);

  const controls = el('div', 'row period-controls');
  controls.append(calendarField, previous, yearField, next, segmentField);

  const actions = el('div', 'row period-actions');
  const wholeMonth = el('button', 'btn btn-secondary', 'Choose this month', { type: 'button' });
  const wholeYear = el('button', 'btn btn-secondary', 'Choose this year', { type: 'button' });
  const range = el('button', 'btn btn-secondary', 'Choose a range of days', {
    type: 'button',
    'aria-pressed': 'false',
  });
  actions.append(wholeMonth, wholeYear);
  if (mode === 'multiple') actions.append(range);

  const status = el('p', 'status-text row-tight', '', { role: 'status' });
  const days = el('div', 'period-days', '', { role: 'group' });
  const note = el('p', 'status-text');
  const chips = el('ul', 'period-chosen');
  const summary = el('p', 'status-text');
  const error = el('p', 'error-text', '', { role: 'alert' });
  error.hidden = true;

  root.append(controls, actions, status, days, note, chips, summary, error);

  function notify() {
    options.onChange?.(chosen);
  }

  function segments() {
    return view?.preview.segments ?? [];
  }

  function currentSegment() {
    return segments().find((segment) => segment.key === segmentKey);
  }

  function calendarName() {
    return calendars.find((calendar) => calendar.id === calendarId)?.name ?? '';
  }

  function pickedFor(coordinate: Coordinate): Picked {
    const segment = segments().find((s) => s.key === coordinate.segment);
    const periodId = view?.saved.get(savedKey(coordinate.segment, coordinate.day));

    return {
      coordinate,
      calendarName: calendarName(),
      ...(segment ? { segmentName: segment.name } : {}),
      ...(periodId ? { periodId } : {}),
    };
  }

  function show() {
    for (const node of [previous, next, yearInput, calendarSelect, segmentSelect]) {
      node.toggleAttribute('disabled', loading);
    }

    status.replaceChildren();
    if (loading) {
      status.append(el('span', 'spinner', '', { 'aria-hidden': 'true' }), 'Loading the year…');
    }

    const segment = currentSegment();

    days.replaceChildren();
    days.setAttribute(
      'aria-label',
      segment ? `Days of ${segment.name} ${year}` : 'Days of the month or festival',
    );

    if (segment) {
      for (const day of segment.days) {
        const coordinate: Coordinate = {
          calendarId,
          year,
          segment: segment.key,
          day: day.date.day,
        };
        const saved = view?.saved.has(savedKey(segment.key, day.date.day)) ?? false;
        const pressed = isSelected(chosen, coordinate);
        const unavailable = !saved && !canCreate;
        const button = el('button', 'btn btn-secondary period-day', String(day.date.day), {
          type: 'button',
          'aria-pressed': String(pressed),
          'aria-label': `${day.date.day} ${segment.name} ${year}${saved ? ', saved' : ''}`,
        });

        if (saved) button.dataset.saved = 'true';
        if (unavailable) button.disabled = true;
        button.addEventListener('click', () => chooseDay(coordinate));
        days.append(button);
      }
    }

    for (const button of [wholeMonth, wholeYear]) button.disabled = loading || !view;
    wholeMonth.setAttribute(
      'aria-pressed',
      String(isSelected(chosen, { calendarId, year, segment: segmentKey })),
    );
    wholeYear.setAttribute('aria-pressed', String(isSelected(chosen, { calendarId, year })));
    range.setAttribute('aria-pressed', String(ranging));
    range.textContent = ranging ? 'Cancel the range' : 'Choose a range of days';

    note.textContent = ranging
      ? anchor
        ? 'Now choose the last day of the range.'
        : 'Choose the first day of the range.'
      : !canCreate
        ? 'A day marked saved already exists. Only someone who can edit this calendar can choose a day that is not saved yet.'
        : 'A day marked saved already exists; choosing any other day creates it when you save.';

    chips.replaceChildren(
      ...chosen.map((picked) => {
        const item = el('li', 'chip');
        const label = periodLabel(picked);
        const drop = el('button', 'chip-remove', '', {
          type: 'button',
          'aria-label': `Remove ${label}`,
        });

        drop.textContent = '×';
        drop.addEventListener('click', () => {
          chosen = remove(chosen, picked.coordinate);
          show();
          notify();
        });
        item.append(
          `${label}${picked.calendarName && calendars.length > 1 ? ` (${picked.calendarName})` : ''}`,
          drop,
        );

        return item;
      }),
    );

    const lines = summarize(chosen);
    const { over } = limit(chosen);

    summary.textContent = chosen.length
      ? `${chosen.length} chosen: ${lines.join('; ')}.`
      : mode === 'single'
        ? 'Nothing chosen.'
        : 'No dates chosen.';

    error.hidden = problem === '' && !over;
    error.textContent = over
      ? `Choose at most ${MAX_SELECTION} dates; this is ${chosen.length}.`
      : problem;
  }

  function fillSegments() {
    segmentSelect.replaceChildren(
      ...segments().map(
        (segment) => new Option(segment.name, segment.key, false, segment.key === segmentKey),
      ),
    );
  }

  async function load(): Promise<void> {
    const mine = ++generation;

    loading = true;
    problem = '';
    show();

    try {
      const loaded = await loadYear(client, tenantId, calendarId, year);

      if (mine !== generation) return;

      view = loaded;

      if (!segments().some((segment) => segment.key === segmentKey)) {
        segmentKey = segments()[0]?.key ?? '';
      }

      fillSegments();
    } catch (cause) {
      if (mine !== generation) return;

      problem = failure(cause);
      view = undefined;
    }

    loading = false;
    show();
  }

  function setYear(value: number) {
    if (!Number.isInteger(value)) return;

    year = value;
    yearInput.value = String(year);
    anchor = undefined;
    void load();
  }

  function chooseDay(coordinate: Coordinate) {
    const segment = coordinate.segment ?? '';
    const day = coordinate.day ?? 0;

    if (ranging) {
      if (!anchor) {
        anchor = { segment, day };
        show();

        return;
      }

      const between = daysBetween(
        segments().map((s) => ({ key: s.key, name: s.name, days: s.days.map((d) => d.date.day) })),
        anchor,
        { segment, day },
      );
      const picked = between
        .map((ref) => pickedFor({ calendarId, year, segment: ref.segment, day: ref.day }))
        .filter((p) => canCreate || p.periodId !== undefined);

      chosen = addAll(chosen, picked);
      anchor = undefined;
      ranging = false;
      show();
      notify();

      return;
    }

    chosen = toggle(chosen, pickedFor(coordinate), mode);
    show();
    notify();
  }

  calendarSelect.addEventListener('change', () => {
    calendarId = calendarSelect.value;
    void (async () => {
      try {
        year = await referenceYear(client, tenantId, calendarId);
      } catch {
        year = 0;
      }

      yearInput.value = String(year);
      segmentKey = '';
      await load();
    })();
  });
  yearInput.addEventListener('change', () => setYear(Number(yearInput.value)));
  previous.addEventListener('click', () => setYear(year - 1));
  next.addEventListener('click', () => setYear(year + 1));
  segmentSelect.addEventListener('change', () => {
    segmentKey = segmentSelect.value;
    anchor = undefined;
    show();
  });
  wholeMonth.addEventListener('click', () => {
    chosen = toggle(chosen, pickedFor({ calendarId, year, segment: segmentKey }), mode);
    show();
    notify();
  });
  wholeYear.addEventListener('click', () => {
    chosen = toggle(chosen, pickedFor({ calendarId, year }), mode);
    show();
    notify();
  });
  range.addEventListener('click', () => {
    ranging = !ranging;
    anchor = undefined;
    show();
  });

  async function start() {
    const initial = options.initial ?? [];
    const [listed, existing] = await Promise.all([
      loadCalendars(client, tenantId),
      initial.length ? loadPeriods(client, tenantId, initial) : Promise.resolve([]),
    ]);

    calendars = listed;

    const byId = new Map(existing.map((period) => [period.entity_id, period]));

    chosen = initial.flatMap((periodId) => {
      const period = byId.get(periodId);

      if (!period) return [];

      const coordinate: Coordinate = {
        calendarId: period.calendar_entity_id,
        year: period.year,
        ...(period.segment ? { segment: period.segment } : {}),
        ...(period.day !== null ? { day: period.day } : {}),
      };

      return [
        {
          coordinate,
          calendarName: period.calendar_name,
          ...(period.segment
            ? { segmentName: segmentNameOf(period.name, period.day !== null) }
            : {}),
          periodId,
        },
      ];
    });

    const first = chosen[0]?.coordinate;

    calendarSelect.replaceChildren(
      ...calendars.map((calendar) => new Option(calendar.name, calendar.id)),
    );
    calendarField.hidden = calendars.length < 2;

    if (calendars.length === 0) {
      loading = false;
      note.textContent = 'There are no calendars available to you here yet.';
      for (const node of [controls, actions]) node.hidden = true;
      show();

      return;
    }

    calendarId = first?.calendarId ?? calendars[0]?.id ?? '';
    calendarSelect.value = calendarId;
    year = first?.year ?? (await referenceYear(client, tenantId, calendarId).catch(() => 0));
    segmentKey = first?.segment ?? '';
    yearInput.value = String(year);
    await load();
  }

  const ready = start().catch((cause) => {
    loading = false;
    problem = failure(cause);
    show();
  });

  show();

  return {
    element: root,
    ready,
    selection: () => chosen,
    setSelection(selection) {
      chosen = [...selection];
      show();
      notify();
    },
    async resolve() {
      const ids = await materializeSelection(client, tenantId, chosen);

      chosen = chosen.map((picked, index) => ({ ...picked, periodId: ids[index] as string }));
      show();

      return ids;
    },
  };
}
