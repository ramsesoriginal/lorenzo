// When the card for a trigger opens and closes (ADR 0264, 0349), apart from how it is drawn, so the
// timing is tested without a browser. A pointer resting on a trigger opens it after a moment;
// leaving closes it after a shorter one that coming back (to the trigger, or onto the card) cancels,
// so a pointer crossing the gap does not make it flicker. Focus opens and blurs close at once,
// Escape closes, and a tap opens it, the next tap on the same trigger following it.

export type Timers = {
  set(run: () => void, ms: number): unknown;
  clear(handle: unknown): void;
};

export type PreviewState<T> = {
  /** The pointer came to `trigger`. */
  enter(trigger: T): void;
  /** The pointer left the trigger or the card. */
  leave(): void;
  /** The pointer is on the card: it stays. */
  holdCard(): void;
  /** `trigger` got keyboard focus. */
  focus(trigger: T): void;
  /** The focus left. */
  blur(): void;
  escape(): void;
  /** Anything else was touched. */
  dismiss(): void;
  /** `trigger` was tapped: true when the tap should follow it, false when it only opened the card. */
  tap(trigger: T): boolean;
  shown(): T | null;
};

export const SHOW_MS = 300;
export const HIDE_MS = 150;

export function createPreviewState<T>(
  open: (trigger: T) => void,
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
  const show = (trigger: T) => {
    stop();
    if (current === trigger) return;
    current = trigger;
    open(trigger);
  };
  const hide = () => {
    stop();
    if (current === null) return;
    current = null;
    close();
  };

  return {
    enter(trigger) {
      timers.clear(closing);
      closing = undefined;
      if (current === trigger) return;
      timers.clear(opening);
      opening = timers.set(() => show(trigger), SHOW_MS);
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
    tap(trigger) {
      if (current === trigger) return true;
      show(trigger);
      return false;
    },
    shown: () => current,
  };
}
