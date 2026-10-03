// Keeps what was last fetched for each key, so it can be shown at once while it's fetched
// again, and only redrawn if it changed. A hover can fetch ahead of the click.

// A fetch this young is recent enough for what follows it, such as the click after a hover.
export const RECENT_MS = 10_000;

export type StaleCache<T> = {
  // What the last fetch of `key` answered, if there was one.
  peek(key: string): T | undefined;
  // The answer for `key`. With a `maxAge` in ms: what's kept if it's younger than that, else a
  // request already running for it, else a new fetch. Without one, always a new fetch - a
  // reload after a change mustn't join a request that started before the change. The newest
  // fetch is what's kept; a failed one keeps what was there.
  refresh(key: string, maxAge?: number): Promise<T>;
  // Fetches `key` unless there's something kept already; failures are ignored.
  prefetch(key: string): void;
};

export function createStaleCache<T>(
  fetch: (key: string) => Promise<T>,
  now: () => number = Date.now,
): StaleCache<T> {
  const kept = new Map<string, { value: T; at: number }>();
  const running = new Map<string, Promise<T>>();
  const newest = new Map<string, number>();
  let started = 0;

  function refresh(key: string, maxAge = 0): Promise<T> {
    const entry = kept.get(key);

    if (maxAge > 0) {
      if (entry && now() - entry.at < maxAge) return Promise.resolve(entry.value);

      const joined = running.get(key);

      if (joined) return joined;
    }

    const turn = ++started;

    newest.set(key, turn);

    const request: Promise<T> = fetch(key)
      .then((value) => {
        if (newest.get(key) === turn) kept.set(key, { value, at: now() });

        return value;
      })
      .finally(() => {
        if (running.get(key) === request) running.delete(key);
      });

    running.set(key, request);

    return request;
  }

  return {
    peek: (key) => kept.get(key)?.value,
    refresh,
    prefetch(key) {
      if (!kept.has(key)) refresh(key, Number.POSITIVE_INFINITY).catch(() => {});
    },
  };
}
