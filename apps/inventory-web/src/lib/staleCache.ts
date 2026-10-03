// Keeps what was last fetched for each key, so it can be shown at once while it's fetched
// again, and only redrawn if it changed. A hover can fetch ahead of the click.

// A fetch this young is recent enough for what follows it, such as the click after a hover.
export const RECENT_MS = 10_000;

export type StaleCache<T> = {
  // What the last fetch of `key` answered, if there was one.
  peek(key: string): T | undefined;
  // The answer for `key`: what's kept if it's younger than `maxAge` ms, else a new fetch, which
  // a request already running for it is shared with. A failed fetch keeps what was there.
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

  function refresh(key: string, maxAge = 0): Promise<T> {
    const entry = kept.get(key);

    if (entry && now() - entry.at < maxAge) return Promise.resolve(entry.value);

    const request =
      running.get(key) ??
      fetch(key)
        .then((value) => {
          kept.set(key, { value, at: now() });
          return value;
        })
        .finally(() => running.delete(key));

    running.set(key, request);

    return request;
  }

  return {
    peek: (key) => kept.get(key)?.value,
    refresh,
    prefetch(key) {
      if (!kept.has(key)) refresh(key).catch(() => {});
    },
  };
}
