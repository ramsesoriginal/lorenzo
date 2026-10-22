// Asking ahead for what a page is likely to ask for next (ADR 0325): bounded, reads only, and
// never anything that writes. Every job is a read through the cache, so what is already held is
// not asked for again, and a failure is the page's to show later, not this.

export type PrefetchLimits = {
  /** Reads running at once. */
  concurrent: number;
  /** Reads waiting their turn. */
  queued: number;
  /** Distinct intentions in one view. */
  intents: number;
};

const DEFAULT_LIMITS: PrefetchLimits = { concurrent: 2, queued: 8, intents: 16 };

export type PrefetchQueue = {
  /** Queues `job` under `key`; dropped when the key was seen, or a limit is reached. */
  enqueue(key: string, job: () => Promise<unknown>): boolean;
  /** A new view: forget what was queued and seen. */
  reset(): void;
};

export function createPrefetchQueue(limits: Partial<PrefetchLimits> = {}): PrefetchQueue {
  const { concurrent, queued, intents } = { ...DEFAULT_LIMITS, ...limits };
  const waiting: Array<() => Promise<unknown>> = [];
  const seen = new Set<string>();
  let active = 0;

  function pump() {
    while (active < concurrent && waiting.length) {
      const job = waiting.shift();

      if (!job) break;

      active++;
      void job()
        .catch(() => {})
        .finally(() => {
          active--;
          pump();
        });
    }
  }

  return {
    enqueue(key, job) {
      if (seen.has(key) || seen.size >= intents || waiting.length >= queued) return false;

      seen.add(key);
      waiting.push(job);
      pump();

      return true;
    },
    reset() {
      waiting.length = 0;
      seen.clear();
    },
  };
}

export type LinkIntentOptions = {
  /** How long the pointer rests on a link before it counts as going there. */
  delayMs?: number;
  /** Called for a link on this origin that the person seems about to follow. */
  onIntent(link: HTMLAnchorElement): void;
};

/**
 * Calls `onIntent` when the pointer rests on a link, when the keyboard arrives at one, or when
 * one is touched: the earliest signs of a click, since keyboard and touch have no hover. Returns
 * what undoes it.
 */
export function bindLinkIntent(options: LinkIntentOptions): () => void {
  const delay = options.delayMs ?? 65;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function linkIn(event: Event): HTMLAnchorElement | null {
    const target = event.target;

    return target instanceof Element ? target.closest<HTMLAnchorElement>('a[href]') : null;
  }

  function intend(link: HTMLAnchorElement) {
    if (link.origin !== window.location.origin) return;

    // Where the link already is, nothing is to be asked for.
    if (
      `${link.pathname}${link.search}` === `${window.location.pathname}${window.location.search}`
    ) {
      return;
    }

    options.onIntent(link);
  }

  const over = (event: Event) => {
    const link = linkIn(event);

    clearTimeout(timer);

    if (link) timer = setTimeout(() => intend(link), delay);
  };
  const out = () => clearTimeout(timer);
  const arrive = (event: Event) => {
    const link = linkIn(event);

    if (link) intend(link);
  };

  document.addEventListener('mouseover', over);
  document.addEventListener('mouseout', out);
  document.addEventListener('focusin', arrive);
  document.addEventListener('touchstart', arrive, { passive: true });

  return () => {
    clearTimeout(timer);
    document.removeEventListener('mouseover', over);
    document.removeEventListener('mouseout', out);
    document.removeEventListener('focusin', arrive);
    document.removeEventListener('touchstart', arrive);
  };
}
