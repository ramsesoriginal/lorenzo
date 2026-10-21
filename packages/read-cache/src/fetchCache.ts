// A cache of what an app reads from the API, kept in front of `fetch` so that every typed call
// through it is cached and every write through it invalidates (ADR 0325). It is bounded session
// memory, never an offline grant and never authorization: the API still decides every read and
// write, and what is held is only ever served to the viewer it was read for.
//
// Two kinds of thing are held:
// - Scoped reads (entries, notes, periods, rosters...): in memory only, under a scope that names
//   the viewer, the library, their role and the flags that change what they see. Another scope
//   never sees them. They are served for `freshMs`, and no longer.
// - Identity reads (`/me`, `/tenants`, `/app-links`): who the person is and where they may go, not
//   what a library holds. With `persist` they are also mirrored in the storage given (the tab's
//   `sessionStorage`), so a navigation that reloads the page still has them, and with `staleMs`
//   they are answered at once and read again in the background.
// Private bodies never reach storage: only a policy that says `persist` is mirrored.

export type Policy = {
  /** How long a read is served without asking again. */
  freshMs: number;
  /** Up to this age a read is still served at once, and asked again in the background. */
  staleMs?: number;
  /** An identity read: held across page loads in the storage given, outside any scope. */
  persist?: boolean;
};

export type Limits = {
  entries: number;
  /** Characters of body held in all, counted twice (UTF-16). */
  bytes: number;
  /** A body longer than this (in characters) is not held. */
  bodyBytes: number;
};

export type FetchCacheOptions = {
  fetch?: typeof fetch;
  now?: () => number;
  /** What to do with a URL: null means never hold it. */
  policy(url: URL): Policy | null;
  /** A write that changes nothing (a preview, a comparison) and so invalidates nothing. */
  isPureWrite?(url: URL, method: string): boolean;
  limits?: Partial<Limits>;
  /** Where identity reads are mirrored; none by default. */
  storage?: Storage | null;
  storagePrefix?: string;
};

export type FetchCache = {
  /** A drop-in for `fetch`, for `createLorenzoClient({ fetch })`. */
  fetch: typeof fetch;
  /**
   * The viewer's scope (their id, the library, their role, the flags that change what they see).
   * Reads outside identity are held only once a scope is set; a new scope forgets the old one's.
   */
  configure(scope: string): void;
  /** No scoped read is served or held until `configure` is called again (a page is changing). */
  suspend(): void;
  /** Forgets reads whose path starts with `prefix`, or all scoped and identity reads. */
  invalidate(prefix?: string): void;
  /** Forgets everything, storage included: sign-in, sign-out, a denied read. */
  clear(): void;
  /** Whether scoped reads are held now (a scope is set). */
  scoped(): boolean;
  /** Called when a background read found a different answer than the one served. */
  onRefreshed(handler: (url: string) => void): () => void;
};

type Saved = {
  path: string;
  status: number;
  statusText: string;
  body: string;
  headers: [string, string][];
  at: number;
  identity: boolean;
};

const DEFAULT_LIMITS: Limits = { entries: 64, bytes: 2 * 1024 * 1024, bodyBytes: 256 * 1024 };

export function createFetchCache(options: FetchCacheOptions): FetchCache {
  const fetcher = options.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const now = options.now ?? Date.now;
  const limits: Limits = { ...DEFAULT_LIMITS, ...options.limits };
  const storage = options.storage ?? null;
  const storagePrefix = options.storagePrefix ?? 'lorenzo.reads.';

  const kept = new Map<string, Saved>();
  const running = new Map<string, Promise<Response>>();
  const newest = new Map<string, number>();
  const listeners = new Set<(url: string) => void>();
  let scope: string | null = null;
  let epoch = 0;
  let sequence = 0;
  let bytes = 0;

  function size(saved: Saved): number {
    return saved.body.length * 2;
  }

  function forget(key: string) {
    const old = kept.get(key);

    if (old) bytes -= size(old);

    kept.delete(key);
  }

  function dropStorage(matches: (path: string) => boolean) {
    if (!storage) return;

    try {
      for (const name of Object.keys(storage)) {
        if (!name.startsWith(storagePrefix)) continue;

        const raw = storage.getItem(name);
        const path = raw ? (JSON.parse(raw) as Saved).path : '';

        if (!raw || matches(path)) storage.removeItem(name);
      }
    } catch {
      // Storage that cannot be read holds nothing worth keeping.
    }
  }

  function invalidate(prefix?: string) {
    epoch++;
    running.clear();
    newest.clear();

    for (const [key, saved] of [...kept]) {
      if (prefix === undefined || saved.path.startsWith(prefix)) forget(key);
    }

    dropStorage((path) => prefix === undefined || path.startsWith(prefix));
  }

  function clear() {
    invalidate();
    scope = null;
  }

  function keyFor(url: URL, identity: boolean): string {
    return `${identity ? 'identity' : scope}|${url.origin}${url.pathname}${url.search}`;
  }

  function lookup(key: string, identity: boolean): Saved | undefined {
    const held = kept.get(key);

    if (held) return held;

    if (!identity || !storage) return undefined;

    try {
      const raw = storage.getItem(storagePrefix + key);

      if (!raw) return undefined;

      const saved = JSON.parse(raw) as Saved;

      kept.set(key, saved);
      bytes += size(saved);

      return saved;
    } catch {
      return undefined;
    }
  }

  function store(key: string, saved: Saved) {
    forget(key);
    kept.set(key, saved);
    bytes += size(saved);

    while (kept.size > limits.entries || bytes > limits.bytes) {
      const oldest = kept.keys().next().value;

      if (oldest === undefined) break;

      forget(oldest);
    }

    if (saved.identity && storage) {
      try {
        storage.setItem(storagePrefix + key, JSON.stringify(saved));
      } catch {
        // Full or blocked: held in memory only.
      }
    }
  }

  function respond(saved: Saved): Response {
    return new Response(saved.body, {
      status: saved.status,
      statusText: saved.statusText,
      headers: saved.headers,
    });
  }

  function network(key: string, request: Request, url: URL, policy: Policy, force: boolean) {
    if (!force) {
      const pending = running.get(key);

      if (pending) return pending.then((response) => response.clone());
    }

    const version = epoch;
    const turn = ++sequence;
    const identity = policy.persist === true;

    newest.set(key, turn);

    const pending = (async () => {
      const response = await fetcher(request);

      if (version !== epoch) throw new Error('This view changed. Please retry.');

      if ([401, 403, 404].includes(response.status)) {
        clear();

        return response;
      }

      if (response.status === 200 && newest.get(key) === turn) {
        const body = await response.clone().text();

        if (version === epoch && newest.get(key) === turn && body.length <= limits.bodyBytes) {
          store(key, {
            path: url.pathname,
            status: response.status,
            statusText: response.statusText,
            body,
            headers: [...response.headers],
            at: now(),
            identity,
          });
        }
      }

      return response;
    })();

    running.set(key, pending);

    return pending
      .then((response) => response.clone())
      .finally(() => {
        if (running.get(key) === pending) running.delete(key);
        if (newest.get(key) === turn) newest.delete(key);
      });
  }

  async function revalidate(key: string, request: Request, url: URL, policy: Policy, old: Saved) {
    try {
      const response = await network(key, request, url, policy, true);
      const fresh = kept.get(key);

      if (fresh && fresh.body !== old.body && response.ok) {
        for (const handler of listeners) handler(`${url.pathname}${url.search}`);
      }
    } catch {
      // The older answer stands; the next read may do better.
    }
  }

  const cachedFetch: typeof fetch = async (input, init) => {
    const request = new Request(input as RequestInfo, init);
    const url = new URL(request.url);

    if (request.method !== 'GET') {
      const pure = options.isPureWrite?.(url, request.method) ?? false;

      if (!pure) invalidate();

      try {
        return await fetcher(request);
      } finally {
        if (!pure) invalidate();
      }
    }

    const policy = options.policy(url);

    if (!policy) return fetcher(request);

    const identity = policy.persist === true;

    if (!identity && scope === null) return fetcher(request);

    const key = keyFor(url, identity);
    const force = request.cache === 'reload' || request.cache === 'no-store';
    const saved = force ? undefined : lookup(key, identity);

    if (saved) {
      const age = now() - saved.at;

      if (age < policy.freshMs) {
        kept.delete(key);
        kept.set(key, saved);

        return respond(saved);
      }

      if (policy.staleMs !== undefined && age < policy.staleMs) {
        void revalidate(key, request.clone(), url, policy, saved);

        return respond(saved);
      }
    }

    return network(key, request, url, policy, force);
  };

  return {
    fetch: cachedFetch,
    configure(next) {
      if (next !== scope) {
        // A different viewer, library or role: what was held for the last one is gone, and so is
        // anything read before the scope was known.
        invalidateScoped();
      }

      scope = next;
    },
    suspend() {
      epoch++;
      running.clear();
      newest.clear();
      scope = null;
    },
    invalidate,
    clear,
    scoped: () => scope !== null,
    onRefreshed(handler) {
      listeners.add(handler);

      return () => listeners.delete(handler);
    },
  };

  function invalidateScoped() {
    epoch++;
    running.clear();
    newest.clear();

    for (const [key, saved] of [...kept]) {
      if (!saved.identity) forget(key);
    }
  }
}
