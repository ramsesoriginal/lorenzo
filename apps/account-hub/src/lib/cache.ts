// A cache for what the pages read from the API, so a click shows something at once instead of
// after a round trip: stale-while-revalidate, kept in memory and mirrored in sessionStorage, which
// survives the full page load every click is.
//
// A read of something already held answers from the cache. If what it holds is older than
// FRESH_MS, it also asks again in the background, and when the answer is different, tells the page
// (onCacheRefreshed) so it can paint again. Nothing is held for longer than MAX_AGE_MS.
//
// Kept honest by three rules:
// - Any write that succeeds empties the cache (lib/api.ts), so what a page reads after changing
//   something is never from before it.
// - It is emptied when the session ends or begins (lib/auth.ts), so one person's data is never
//   shown to the next.
// - A reload of the page (F5) asks again for everything it reads, as a reload means.
//
// Personal data sits in sessionStorage while it is held: per tab, gone when the tab is closed, and
// no more readable by a script than the Authgear tokens are.

const STORAGE_PREFIX = 'lorenzo.cache.';

// Within this, a read is not asked again.
const FRESH_MS = 15_000;
// Past this, a held read is not used at all.
const MAX_AGE_MS = 30 * 60_000;

export const CACHE_REFRESHED_EVENT = 'lorenzo:cache-refreshed';

type Entry = { at: number; value: unknown };

const memory = new Map<string, Entry>();
const inFlight = new Map<string, Promise<unknown>>();

// Bumped when the cache is emptied, so an answer that was on its way meanwhile is not kept.
let generation = 0;

// A reload asks again for everything, so nothing held from before this page began counts.
const ignoreBefore = isReload() ? Date.now() : 0;

function isReload(): boolean {
  if (typeof performance === 'undefined' || !performance.getEntriesByType) return false;

  const [navigation] = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[];

  return navigation?.type === 'reload';
}

function storage(): Storage | undefined {
  try {
    return typeof sessionStorage === 'undefined' ? undefined : sessionStorage;
  } catch {
    // Blocked by the browser: the memory alone does it.
    return undefined;
  }
}

function read(key: string): Entry | undefined {
  let entry = memory.get(key);

  if (!entry) {
    try {
      const stored = storage()?.getItem(STORAGE_PREFIX + key);

      if (stored) {
        entry = JSON.parse(stored) as Entry;
        memory.set(key, entry);
      }
    } catch {
      return undefined;
    }
  }

  if (!entry || entry.at < ignoreBefore || Date.now() - entry.at > MAX_AGE_MS) return undefined;

  return entry;
}

function write(key: string, value: unknown): void {
  const entry: Entry = { at: Date.now(), value };

  memory.set(key, entry);

  try {
    storage()?.setItem(STORAGE_PREFIX + key, JSON.stringify(entry));
  } catch {
    // Full, or blocked: held in memory only.
  }
}

// Asks, once at a time for a key, and keeps the answer unless the cache was emptied meanwhile.
function load<T>(key: string, fetch: () => Promise<T>): Promise<T> {
  const running = inFlight.get(key);

  if (running) return running as Promise<T>;

  const started = generation;
  const request = fetch()
    .then((value) => {
      if (started === generation) write(key, value);

      return value;
    })
    .finally(() => {
      if (inFlight.get(key) === request) inFlight.delete(key);
    });

  inFlight.set(key, request);

  return request;
}

// `fetch` is the real call. `force` skips what is held, for a read that is itself a refresh.
export function cached<T>(
  key: string,
  fetch: () => Promise<T>,
  { force = false }: { force?: boolean } = {},
): Promise<T> {
  const entry = force ? undefined : read(key);

  if (!entry) return load(key, fetch);

  if (Date.now() - entry.at > FRESH_MS) {
    // Held, but old: answered now, and asked again for the next one. A page that is showing the
    // old answer is told if it was different.
    void load(key, fetch)
      .then((fresh) => {
        if (JSON.stringify(fresh) !== JSON.stringify(entry.value)) {
          window.dispatchEvent(new CustomEvent(CACHE_REFRESHED_EVENT, { detail: { key } }));
        }
      })
      .catch(() => {
        // The old answer stands; the next read may do better.
      });
  }

  return Promise.resolve(entry.value as T);
}

// Empties the cache: after a write, and when the session begins or ends.
export function clearCache(): void {
  generation += 1;
  memory.clear();
  inFlight.clear();

  try {
    const store = storage();

    if (!store) return;

    for (const key of Object.keys(store)) {
      if (key.startsWith(STORAGE_PREFIX)) store.removeItem(key);
    }
  } catch {
    // Nothing to empty it from.
  }
}

// Calls `handler` when a held answer turned out to be out of date, for the page to read again. Several
// at once (a page reads several things) come as one call.
export function onCacheRefreshed(handler: () => void): void {
  let pending: ReturnType<typeof setTimeout> | undefined;

  window.addEventListener(CACHE_REFRESHED_EVENT, () => {
    clearTimeout(pending);
    pending = setTimeout(handler, 50);
  });
}
