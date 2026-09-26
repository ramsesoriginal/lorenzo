import { describe, expect, it, vi } from 'vitest';
import {
  createLorenzoClient,
  etagOf,
  fetchAllPages,
  LorenzoApiError,
  type Page,
  toLorenzoApiError,
  unwrap,
} from '../src/index';

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });

describe('toLorenzoApiError', () => {
  it("uses the problem's detail, and keeps its type and every field", () => {
    const error = toLorenzoApiError(
      {
        type: 'capacity-exceeded',
        title: 'Conflict',
        detail: 'The Backpack would hold 34 of its 30.',
        limit: 30,
      },
      409,
    );
    expect(error).toBeInstanceOf(LorenzoApiError);
    expect(error.message).toBe('The Backpack would hold 34 of its 30.');
    expect(error.status).toBe(409);
    expect(error.problemType).toBe('capacity-exceeded');
    expect(error.problem.limit).toBe(30);
  });

  it('falls back to the title, then to the status', () => {
    expect(toLorenzoApiError({ title: 'Not Found' }, 404).message).toBe('Not Found');
    expect(toLorenzoApiError('<html>', 502).message).toBe('Request failed (502).');
    expect(toLorenzoApiError(undefined, 500).problem).toEqual({});
  });
});

describe('unwrap', () => {
  it('returns the data', async () => {
    await expect(unwrap({ data: { id: 'a' }, response: json({}) })).resolves.toEqual({ id: 'a' });
  });

  it('throws the error, with the response status', async () => {
    const failed = unwrap({ error: { detail: 'Gone.' }, response: json({}, 410) });
    await expect(failed).rejects.toMatchObject({ message: 'Gone.', status: 410 });
  });
});

describe('createLorenzoClient', () => {
  it('sends the access token with every request', async () => {
    const fetch = vi.fn(async (_request: Request) => json({ id: 'me' }));
    const client = createLorenzoClient({
      baseUrl: 'https://api.example',
      getAccessToken: async () => 'token-1',
      fetch,
    });
    await client.GET('/me');
    const request = fetch.mock.calls[0]?.[0];
    expect(request?.url).toBe('https://api.example/me');
    expect(request?.headers.get('Authorization')).toBe('Bearer token-1');
  });

  it("refuses before sending when there's no token", async () => {
    const fetch = vi.fn(async (_request: Request) => json({}));
    const client = createLorenzoClient({
      baseUrl: 'https://api.example',
      getAccessToken: () => null,
      fetch,
    });
    await expect(client.GET('/me')).rejects.toMatchObject({ status: 401 });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("leaves Authorization to the caller when there's no token source", async () => {
    const fetch = vi.fn(async (_request: Request) => json({}));
    const client = createLorenzoClient({ baseUrl: 'https://api.example', fetch });
    await client.GET('/me', { headers: { Authorization: 'Bearer per-call' } });
    expect(fetch.mock.calls[0]?.[0].headers.get('Authorization')).toBe('Bearer per-call');
  });
});

describe('fetchAllPages', () => {
  const page = (n: number, pages: number): Page<number> => ({
    items: [n * 10, n * 10 + 1],
    total: pages * 2,
    page: n,
    size: 2,
    pages,
  });

  it('asks once when there is one page', async () => {
    const getPage = vi.fn(async (n: number) => page(n, 1));
    await expect(fetchAllPages(getPage)).resolves.toEqual([10, 11]);
    expect(getPage).toHaveBeenCalledTimes(1);
  });

  it('returns every page, in order', async () => {
    await expect(fetchAllPages(async (n) => page(n, 3))).resolves.toEqual([10, 11, 20, 21, 30, 31]);
  });
});

describe('etagOf', () => {
  it('reads the ETag header, or null', () => {
    expect(etagOf(json({}, 200, { ETag: 'W/"2026-09-26T10:00:00Z"' }))).toBe(
      'W/"2026-09-26T10:00:00Z"',
    );
    expect(etagOf(json({}))).toBeNull();
  });
});
