// When the card for a link opens and closes (ADR 0264), apart from how it is drawn, so the timing
// is tested without a browser. A pointer resting on a link opens it after a moment; leaving
// closes it after a shorter one that coming back (to the link, or onto the card) cancels, so a
// pointer crossing the gap does not make it flicker. Focus opens and blurs close at once, Escape
// closes, and a tap opens it, the next tap on the same link following it.

export type Timers = {
  set(run: () => void, ms: number): unknown;
  clear(handle: unknown): void;
};

export type PreviewState<T> = {
  /** The pointer came to `link`. */
  enter(link: T): void;
  /** The pointer left the link or the card. */
  leave(): void;
  /** The pointer is on the card: it stays. */
  holdCard(): void;
  /** `link` got keyboard focus. */
  focus(link: T): void;
  /** The focus left. */
  blur(): void;
  escape(): void;
  /** Anything else was touched. */
  dismiss(): void;
  /** `link` was tapped: true when the tap should follow it, false when it only opened the card. */
  tap(link: T): boolean;
  shown(): T | null;
};

export const SHOW_MS = 300;
export const HIDE_MS = 150;

export function createPreviewState<T>(
  open: (link: T) => void,
  close: () => void,
  timers: Timers = {
    set: (run, ms) => setTimeout(run, ms),
    clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
  },
): PreviewState<T> {
  let current: T | null = null;
  let opening: unknown;
  let closing: unknown;

  const stop = () => {
    timers.clear(opening);
    timers.clear(closing);
    opening = closing = undefined;
  };
  const show = (link: T) => {
    stop();
    if (current === link) return;
    current = link;
    open(link);
  };
  const hide = () => {
    stop();
    if (current === null) return;
    current = null;
    close();
  };

  return {
    enter(link) {
      timers.clear(closing);
      closing = undefined;
      if (current === link) return;
      timers.clear(opening);
      opening = timers.set(() => show(link), SHOW_MS);
    },
    leave() {
      timers.clear(opening);
      opening = undefined;
      if (current === null) return;
      timers.clear(closing);
      closing = timers.set(hide, HIDE_MS);
    },
    holdCard() {
      timers.clear(closing);
      closing = undefined;
    },
    focus: show,
    blur: hide,
    escape: hide,
    dismiss: hide,
    tap(link) {
      if (current === link) return true;
      show(link);
      return false;
    },
    shown: () => current,
  };
}
