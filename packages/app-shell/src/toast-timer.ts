// The countdown of a toast that leaves by itself (ADR 0415): ten seconds, which pause while the
// pointer is over it or focus is in it, and start again from the full ten when they leave. Pure
// apart from the timers it is given, so it is tested with fake ones.

export type ToastTimer = {
  start(): void;
  /** Stop counting: the pointer is over the toast, or focus is in it. */
  hold(): void;
  /** Count again from the full time. */
  release(): void;
  stop(): void;
};

export function createToastTimer(ms: number, onDone: () => void): ToastTimer {
  let id: ReturnType<typeof setTimeout> | null = null;

  const clear = () => {
    if (id !== null) clearTimeout(id);
    id = null;
  };
  const begin = () => {
    clear();
    id = setTimeout(() => {
      id = null;
      onDone();
    }, ms);
  };

  return { start: begin, hold: clear, release: begin, stop: clear };
}
