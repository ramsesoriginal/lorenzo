import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./auth', () => ({
  getAccessToken: vi.fn().mockResolvedValue('test-token'),
}));

import { apiFetchAllPages } from './api';

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

// Regression coverage for the pagination bug: apps/api's list endpoints are
// all paginated (ADR 0020 - default page size 50, capped at 100), and
// nothing on this app's read side ever followed a `pages` value past 1 -
// a catalog (or "used as prototype by" reverse lookup) with more than one
// page's worth of items silently lost everything past the first page.
describe('apiFetchAllPages', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns the items from a single page without fetching more', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [{ id: 1 }, { id: 2 }], total: 2, page: 1, size: 100, pages: 1 }),
    );
    const result = await apiFetchAllPages('/tenants/t/items');
    expect(result).toEqual([{ id: 1 }, { id: 2 }]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/tenants\/t\/items\?size=100$/);
  });

  it('fetches every remaining page and flattens them in original order', async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ items: [{ id: 1 }], total: 3, page: 1, size: 1, pages: 3 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ items: [{ id: 2 }], total: 3, page: 2, size: 1, pages: 3 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ items: [{ id: 3 }], total: 3, page: 3, size: 1, pages: 3 }),
      );

    const result = await apiFetchAllPages('/tenants/t/items');

    expect(result).toEqual([{ id: 1 }, { id: 2 }, { id: 3 }]);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls[0]).toMatch(/\/tenants\/t\/items\?size=100$/);
    expect(urls[1]).toMatch(/\/tenants\/t\/items\?size=100&page=2$/);
    expect(urls[2]).toMatch(/\/tenants\/t\/items\?size=100&page=3$/);
  });

  it('appends the page params with & when the path already has a query string', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [{ id: 1 }], total: 1, page: 1, size: 100, pages: 1 }),
    );
    await apiFetchAllPages('/tenants/t/items?q=sword');
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/tenants\/t\/items\?q=sword&size=100$/);
  });

  it('returns an empty array for an empty result set without fetching a second page', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [], total: 0, page: 1, size: 100, pages: 0 }),
    );
    const result = await apiFetchAllPages('/tenants/t/items');
    expect(result).toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
