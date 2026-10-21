/** Bounded session memory, never an offline permission grant (ADR 0313). */
export function createReadCache(
  fetcher: typeof fetch = (...args) => fetch(...args),
  now = Date.now,
) {
  type Saved = { body: string; headers: [string, string][]; at: number };
  const kept = new Map<string, Saved>();
  const running = new Map<string, Promise<Response>>();
  const newest = new Map<string, number>();
  let scope = '';
  let tenant = '';
  let authorized = false;
  let retain = false;
  let epoch = 0;
  let sequence = 0;
  let bytes = 0;
  function invalidate() {
    epoch++;
    kept.clear();
    running.clear();
    newest.clear();
    bytes = 0;
  }
  function remove(key: string) {
    const old = kept.get(key);
    if (old) bytes -= old.body.length * 2;
    kept.delete(key);
  }
  function suspend() {
    epoch++;
    authorized = false;
    running.clear();
    newest.clear();
  }
  function clear() {
    invalidate();
    scope = '';
    tenant = '';
    authorized = false;
    retain = false;
  }
  return {
    suspend,
    clear,
    invalidate,
    canPrefetch: () => authorized && retain,
    configure(viewer: string, tenantId: string, visibility: string, fullVisibility: boolean) {
      const next = JSON.stringify([viewer, tenantId, visibility, fullVisibility]);
      if (next !== scope || !fullVisibility) invalidate();
      scope = next;
      tenant = tenantId;
      authorized = true;
      retain = fullVisibility;
    },
    async fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
      const request = new Request(input, init);
      const url = new URL(request.url);
      const read = request.method === 'GET';
      const pure =
        url.pathname.endsWith('/calendar-references/resolve') ||
        url.pathname.endsWith('/preview') ||
        url.pathname.endsWith('/events/compare');
      if (!read) {
        if (!pure) invalidate();
        try {
          return await fetcher(request);
        } finally {
          if (!pure) invalidate();
        }
      }
      const eligible =
        authorized &&
        url.pathname.startsWith(`/tenants/${tenant}/`) &&
        !url.pathname.endsWith('/events/access') &&
        !url.pathname.endsWith('/entities/resolve') &&
        !url.pathname.includes('/entities/by-slug/');
      if (!eligible) return fetcher(request);
      const key = scope + url.pathname + url.search;
      const force = ['reload', 'no-store'].includes(request.cache);
      const saved = kept.get(key);
      if (retain && !force && saved && now() - saved.at < 10000) {
        kept.delete(key);
        kept.set(key, saved);
        return new Response(saved.body, { status: 200, headers: saved.headers });
      }
      if (!force) {
        const pending = running.get(key);
        if (pending) return (await pending).clone();
      }
      const version = epoch;
      const turn = ++sequence;
      newest.set(key, turn);
      const pending = (async () => {
        const response = await fetcher(request);
        if (version !== epoch) throw new Error('This view changed. Please retry.');
        if ([401, 403, 404].includes(response.status)) {
          clear();
          return response;
        }
        if (response.ok && retain && newest.get(key) === turn) {
          const body = await response.clone().text();
          if (version === epoch && newest.get(key) === turn && body.length <= 262144) {
            remove(key);
            kept.set(key, { body, headers: [...response.headers], at: now() });
            bytes += body.length * 2;
            while (kept.size > 64 || bytes > 2097152) {
              const oldest = kept.keys().next().value;
              if (oldest === undefined) break;
              remove(oldest);
            }
          }
        }
        return response;
      })();
      running.set(key, pending);
      try {
        return (await pending).clone();
      } finally {
        if (running.get(key) === pending) running.delete(key);
        if (newest.get(key) === turn) newest.delete(key);
      }
    },
  };
}
export const calendarReads = createReadCache();
