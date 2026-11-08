import {
  describe,
  indexOf,
  keyTarget,
  moved,
  placeAt,
  type StripSegment,
  totalDays,
} from './strip';

export * from './strip';

export interface TimeFilterOptions {
  /** The segments of the year, in the calendar's order. */
  segments: StripSegment[];
  /** The days that have something on them, as [segment key, day]: each is a tick on the strip. */
  marks?: Array<[string, number]>;
  /** Called with a range of places on the strip, or null for any time. */
  onChange: (range: { from: number; to: number } | null) => void;
  initial?: { from: number; to: number } | null;
}

export interface TimeFilter {
  element: HTMLElement;
  range(): { from: number; to: number } | null;
  set(range: { from: number; to: number } | null): void;
}

function node<K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = '') {
  const made = document.createElement(tag);
  if (className) made.className = className;
  if (text) made.textContent = text;
  return made;
}

/** The strip: a segment bar, a tick for each marked day, and one handle for each end of a range. */
export function createTimeFilter(options: TimeFilterOptions): TimeFilter {
  const { segments, onChange } = options;
  const total = totalDays(segments);
  let current = options.initial ?? null;
  const root = node('div', 'time-filter');
  const head = node('div', 'time-filter-head');
  const out = node('span', 'time-filter-out');
  out.setAttribute('aria-live', 'polite');
  const clear = node('button', 'btn btn-text', 'Any time');
  clear.type = 'button';
  head.append(node('b', '', 'When'), out, clear);
  const strip = node('div', 'time-filter-strip');
  const bar = node('div', 'time-filter-segs');
  for (const s of segments) {
    const part = node('span', 'time-filter-seg');
    if (s.festival) part.dataset.mark = 'festival';
    part.style.flex = String(s.days);
    part.title = s.name;
    part.append(node('span', s.days / total < 0.06 ? 'visually-hidden' : '', s.name));
    bar.append(part);
  }
  const ticks = node('div', 'time-filter-marks');
  ticks.setAttribute('aria-hidden', 'true');
  const placed = new Map<number, number>();
  for (const [key, day] of options.marks ?? []) {
    const at = indexOf(segments, key, day);
    if (at !== null) placed.set(at, (placed.get(at) ?? 0) + 1);
  }
  const pct = (at: number) => (total > 1 ? ((at - 1) / (total - 1)) * 100 : 0);
  for (const [at, count] of placed) {
    const tick = node('i');
    tick.style.left = `${pct(at)}%`;
    // The more is dated on a day, the taller its tick: a density, not a count of what is hidden.
    tick.style.height = `${Math.min(16, 5 + count * 3)}px`;
    ticks.append(tick);
  }
  const band = node('div', 'time-filter-range');
  const handles = (['from', 'to'] as const).map((which) => {
    const handle = node('button', `time-filter-handle ${which}`);
    handle.type = 'button';
    handle.setAttribute('role', 'slider');
    handle.dataset.which = which;
    handle.setAttribute('aria-label', which === 'from' ? 'From' : 'To');
    handle.setAttribute('aria-valuemin', '1');
    handle.setAttribute('aria-valuemax', String(total));
    return handle;
  });
  strip.append(bar, ticks, band, ...handles);
  const note = node(
    'p',
    'caption',
    'Drag across the year, or use the arrow keys, Page Up, Page Down, Home and End on a handle. It narrows the list below and changes nothing in the data.',
  );
  root.append(head, strip, note);

  function draw() {
    out.textContent = describe(segments, current);
    // With no range the handles stand at the two ends of the year, as drawn: any time is the whole year.
    const shown = current ?? { from: 1, to: total };
    clear.hidden = !current;
    band.hidden = false;
    for (const handle of handles) {
      const value = shown[handle.dataset.which as 'from' | 'to'];
      handle.style.left = `${pct(value)}%`;
      handle.setAttribute('aria-valuenow', String(value));
      handle.setAttribute('aria-valuetext', describe(segments, { from: value, to: value }));
    }
    band.style.left = `${pct(shown.from)}%`;
    band.style.width = `${pct(shown.to) - pct(shown.from)}%`;
  }
  function apply(next: { from: number; to: number } | null) {
    // A range that takes in the whole year is any time.
    current = next && next.from === 1 && next.to === total ? null : next;
    draw();
    onChange(current);
  }
  clear.addEventListener('click', () => apply(null));
  let dragging: 'from' | 'to' | null = null;
  const place = (event: PointerEvent) => {
    const box = strip.getBoundingClientRect();
    return placeAt((event.clientX - box.left) / (box.width || 1), total);
  };
  strip.addEventListener('pointerdown', (event) => {
    const value = place(event);
    const grabbed = (event.target as HTMLElement).dataset?.which as 'from' | 'to' | undefined;
    const start = current ?? { from: value, to: value };
    const which =
      grabbed ?? (Math.abs(value - start.from) <= Math.abs(value - start.to) ? 'from' : 'to');
    dragging = which;
    strip.setPointerCapture?.(event.pointerId);
    apply(moved(start, which, value));
    event.preventDefault();
  });
  strip.addEventListener('pointermove', (event) => {
    if (dragging) apply(moved(current ?? { from: 1, to: total }, dragging, place(event)));
  });
  const stop = () => {
    dragging = null;
  };
  strip.addEventListener('pointerup', stop);
  strip.addEventListener('pointercancel', stop);
  strip.addEventListener('keydown', (event) => {
    const handle = event.target as HTMLElement;
    const which = handle.dataset?.which as 'from' | 'to' | undefined;
    if (!which) return;
    const from = current ?? { from: 1, to: total };
    const next = keyTarget(event.key, from[which], total);
    if (next === null) return;
    event.preventDefault();
    apply(moved(from, which, next));
    // Moving an end past the other drags the other along; the handle keeps the focus.
    strip.querySelector<HTMLElement>(`[data-which="${which}"]`)?.focus();
  });
  draw();
  return {
    element: root,
    range: () => current,
    set(range) {
      current = range;
      draw();
    },
  };
}
