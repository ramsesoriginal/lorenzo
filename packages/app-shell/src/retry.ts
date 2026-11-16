// A failed read tries again by itself, a few times and with a short wait that grows, and says so
// (ADR 0413). A write is never retried automatically: it may have arrived, and doing it twice is
// worse than asking. This is only for reads, and its name says so.

/** The wait before attempt `n` (1 is the first retry), doubling from `base` up to `max`. */
export function backoffMs(attempt: number, base = 1000, max = 8000): number {
  return Math.min(max, base * 2 ** Math.max(0, attempt - 1));
}

export type RetryReadOptions = {
  /** How many tries in all, the first included. */
  tries?: number;
  base?: number;
  max?: number;
  /** Called before each wait, so the page can say "Trying again in a moment (2)". */
  onRetry?(info: { attempt: number; tries: number; waitMs: number; error: unknown }): void;
  /** Stop trying at once (a request that was cancelled, a person who navigated away). */
  signal?: AbortSignal;
};

/** Run a read; on failure wait and run it again, and after the last try throw the last error. */
export async function retryRead<T>(
  read: () => Promise<T>,
  options: RetryReadOptions = {},
): Promise<T> {
  const tries = options.tries ?? 4;

  for (let attempt = 1; ; attempt++) {
    try {
      return await read();
    } catch (error) {
      if (attempt >= tries || options.signal?.aborted) throw error;

      const waitMs = backoffMs(attempt, options.base, options.max);

      options.onRetry?.({ attempt, tries, waitMs, error });
      await new Promise<void>((resolve) => setTimeout(resolve, waitMs));
      if (options.signal?.aborted) throw error;
    }
  }
}
