import { describe, expect, it } from 'vitest';
import { createFetchCache, type Policy } from '../src/fetchCache';

const API = 'https://api.example.test';

class FakeStorage {
  getItem(key: string): string | null {
    return Object.hasOwn(this, key)
      ? ((this as unknown as Record<string, string>)[key] ?? null)
      : null;
  }
  setItem(key: string, value: string) {
    (this as unknown as Record<string, string>)[key] = value;
  }
  removeItem(key: string) {
    delete (this as unknown as Record<string, string>)[key];
  }
}

const identityOrScoped = (url: URL): Policy | null =>
  url.pathname.startsWith('/me')
    ? { freshMs: 15_000, staleMs: 600_000, persist: true }
    : { freshMs: 10_000 };

function setup(
  policy: (url: URL) => Policy | null = identityOrScoped,
  extra: Partial<Parameters<typeof createFetchCache>[0]> = {},
) {
  const calls: string[] = [];
  const answers = new Map<string, string>();
  let clock = 0;
  const fetcher = async (input: RequestInfo | URL) => {
    const request = input as Request;
    const url = new URL(request.url);

    calls.push(`${request.method} ${url.pathname}${url.search}`);

    return new Response(answers.get(url.pathname) ?? JSON.stringify({ path: url.pathname }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  const cache = createFetchCache({
    fetch: fetcher as typeof fetch,
    now: () => clock,
    policy,
    ...extra,
  });

  return {
    cache,
    calls,
    answers,
    advance: (ms: number) => {
      clock += ms;
    },
    get: (path: string, init?: RequestInit) => cache.fetch(`${API}${path}`, init),
  };
}

describe('scoped reads', () => {
  it('are held for the fresh time, and asked again after it', async () => {
    const t = setup();

    t.cache.configure('viewer-1');
    await t.get('/tenants/a/entities/1');
    await t.get('/tenants/a/entities/1');
    expect(t.calls).toEqual(['GET /tenants/a/entities/1']);
    t.advance(10_001);
    await t.get('/tenants/a/entities/1');
    expect(t.calls).toHaveLength(2);
  });

  it('are not held before a scope is set, or while suspended', async () => {
    const t = setup();

    await t.get('/tenants/a/entities/1');
    await t.get('/tenants/a/entities/1');
    expect(t.calls).toHaveLength(2);
    t.cache.configure('viewer-1');
    await t.get('/tenants/a/entities/1');
    t.cache.suspend();
    await t.get('/tenants/a/entities/1');
    expect(t.calls).toHaveLength(4);
  });

  it('are never served to another scope', async () => {
    const t = setup();

    t.cache.configure('viewer-1');
    await t.get('/tenants/a/entities/1');
    t.cache.configure('viewer-2');
    await t.get('/tenants/a/entities/1');
    expect(t.calls).toHaveLength(2);
    t.cache.configure('viewer-2');
    await t.get('/tenants/a/entities/1');
    expect(t.calls).toHaveLength(2);
  });

  it('share one request while it is running', async () => {
    const t = setup();

    t.cache.configure('viewer-1');
    const [a, b] = await Promise.all([t.get('/tenants/a/x'), t.get('/tenants/a/x')]);

    expect(t.calls).toHaveLength(1);
    expect(await a.json()).toEqual(await b.json());
  });

  it('are asked again when the request says so', async () => {
    const t = setup();

    t.cache.configure('viewer-1');
    await t.get('/tenants/a/x');
    await t.get('/tenants/a/x', { cache: 'no-store' });
    expect(t.calls).toHaveLength(2);
  });

  it('are not held for a URL the policy refuses', async () => {
    const t = setup((url) =>
      url.pathname.endsWith('/events/access') ? null : { freshMs: 10_000 },
    );

    t.cache.configure('viewer-1');
    await t.get('/tenants/a/events/access');
    await t.get('/tenants/a/events/access');
    expect(t.calls).toHaveLength(2);
  });
});

describe('writes', () => {
  it('invalidate before and after the request', async () => {
    const t = setup();

    t.cache.configure('viewer-1');
    await t.get('/tenants/a/x');
    await t.get('/tenants/a/x', {});
    expect(t.calls).toHaveLength(1);
    await t.get('/tenants/a/x', { method: 'POST', body: '{}' });
    await t.get('/tenants/a/x');
    expect(t.calls).toEqual(['GET /tenants/a/x', 'POST /tenants/a/x', 'GET /tenants/a/x']);
  });

  it('that change nothing leave the reads alone', async () => {
    const t = setup(undefined, { isPureWrite: (url) => url.pathname.endsWith('/preview') });

    t.cache.configure('viewer-1');
    await t.get('/tenants/a/x');
    await t.get('/tenants/a/preview', { method: 'POST', body: '{}' });
    await t.get('/tenants/a/x');
    expect(t.calls).toEqual(['GET /tenants/a/x', 'POST /tenants/a/preview']);
  });

  it('keep a read that began before them from filling the cache', async () => {
    const calls: string[] = [];
    let release: (() => void) | undefined;
    const slow = (input: RequestInfo | URL) => {
      const request = input as Request;

      calls.push(request.method);

      return new Promise<Response>((resolve) => {
        const respond = () => resolve(new Response('"old"', { status: 200 }));

        if (request.method === 'GET' && calls.filter((c) => c === 'GET').length === 1) {
          release = respond;
        } else {
          respond();
        }
      });
    };
    const cache = createFetchCache({
      fetch: slow as typeof fetch,
      policy: () => ({ freshMs: 10_000 }),
    });

    cache.configure('viewer-1');
    const first = cache.fetch(`${API}/tenants/a/x`);

    await cache.fetch(`${API}/tenants/a/x`, { method: 'POST', body: '{}' });
    release?.();
    await expect(first).rejects.toThrow('This view changed');
    await cache.fetch(`${API}/tenants/a/x`);
    expect(calls.filter((c) => c === 'GET')).toHaveLength(2);
  });
});

describe('limits and refusals', () => {
  it('hold at most the entries allowed, the oldest going first', async () => {
    const t = setup(undefined, { limits: { entries: 2 } });

    t.cache.configure('viewer-1');
    await t.get('/tenants/a/1');
    await t.get('/tenants/a/2');
    await t.get('/tenants/a/3');
    await t.get('/tenants/a/3');
    await t.get('/tenants/a/1');
    expect(t.calls).toEqual([
      'GET /tenants/a/1',
      'GET /tenants/a/2',
      'GET /tenants/a/3',
      'GET /tenants/a/1',
    ]);
  });

  it('do not hold a body over the size allowed', async () => {
    const t = setup(undefined, { limits: { bodyBytes: 10 } });

    t.answers.set('/tenants/a/big', 'x'.repeat(50));
    t.cache.configure('viewer-1');
    await t.get('/tenants/a/big');
    await t.get('/tenants/a/big');
    expect(t.calls).toHaveLength(2);
  });

  it('forget everything when the API answers 404', async () => {
    const calls: string[] = [];
    const fetcher = async (input: RequestInfo | URL) => {
      const url = new URL((input as Request).url);

      calls.push(url.pathname);

      return new Response('{}', { status: url.pathname.endsWith('/gone') ? 404 : 200 });
    };
    const cache = createFetchCache({
      fetch: fetcher as typeof fetch,
      policy: () => ({ freshMs: 10_000 }),
    });

    cache.configure('viewer-1');
    await cache.fetch(`${API}/tenants/a/x`);
    await cache.fetch(`${API}/tenants/a/gone`);
    expect(cache.scoped()).toBe(false);
    await cache.fetch(`${API}/tenants/a/x`);
    expect(calls).toEqual(['/tenants/a/x', '/tenants/a/gone', '/tenants/a/x']);
  });

  it('invalidate only a prefix when given one', async () => {
    const t = setup();

    t.cache.configure('viewer-1');
    await t.get('/tenants/a/calendars/1');
    await t.get('/tenants/a/entities/1');
    t.cache.invalidate('/tenants/a/calendars');
    await t.get('/tenants/a/calendars/1');
    await t.get('/tenants/a/entities/1');
    expect(t.calls).toEqual([
      'GET /tenants/a/calendars/1',
      'GET /tenants/a/entities/1',
      'GET /tenants/a/calendars/1',
    ]);
  });
});

describe('identity reads', () => {
  it('survive a page load in the storage given, and nothing private does', async () => {
    const storage = new FakeStorage() as unknown as Storage;
    const first = setup(undefined, { storage });

    first.cache.configure('viewer-1');
    await first.get('/me');
    await first.get('/tenants/a/entities/1');
    expect(Object.keys(storage)).toHaveLength(1);
    expect(Object.keys(storage)[0]).toContain('/me');

    // A new page: a new cache over the same storage.
    const second = setup(undefined, { storage });

    await second.get('/me');
    expect(second.calls).toEqual([]);
  });

  it('are served at once when stale and read again, telling the page when they changed', async () => {
    const t = setup();
    const told: string[] = [];

    t.cache.onRefreshed((url) => told.push(url));
    await t.get('/me');
    t.answers.set('/me', JSON.stringify({ changed: true }));
    t.advance(20_000);
    const stale = await t.get('/me');

    expect(await stale.json()).toEqual({ path: '/me' });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(t.calls).toEqual(['GET /me', 'GET /me']);
    expect(told).toEqual(['/me']);
    expect(await (await t.get('/me')).json()).toEqual({ changed: true });
  });

  it('are held without a scope, and forgotten by clear', async () => {
    const storage = new FakeStorage() as unknown as Storage;
    const t = setup(undefined, { storage });

    await t.get('/me');
    await t.get('/me');
    expect(t.calls).toHaveLength(1);
    t.cache.clear();
    expect(Object.keys(storage)).toHaveLength(0);
    await t.get('/me');
    expect(t.calls).toHaveLength(2);
  });
});
