import { describe, expect, it, vi } from 'vitest';

// api.ts imports lib/auth, which reaches @authgear/web - browser-only at
// import time.
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

import { fetchAllPages } from './api';
import type { Page } from './types';

function page<T>(items: T[], pageNumber: number, pages: number): Page<T> {
  return { items, total: items.length, page: pageNumber, size: 100, pages };
}

// Regression coverage for the pagination bug: apps/api's list endpoints are
// all paginated (ADR 0020 - default page size 50, capped at 100), and
// nothing on this app's read side ever followed a `pages` value past 1 -
// a catalog (or "used as prototype by" reverse lookup) with more than one
// page's worth of items silently lost everything past the first page.
describe('fetchAllPages', () => {
  it('returns the items from a single page without fetching more', async () => {
    const getPage = vi.fn().mockResolvedValueOnce(page([{ id: 1 }, { id: 2 }], 1, 1));
    expect(await fetchAllPages(getPage)).toEqual([{ id: 1 }, { id: 2 }]);
    expect(getPage).toHaveBeenCalledTimes(1);
    expect(getPage).toHaveBeenCalledWith(1);
  });

  it('fetches every remaining page and flattens them in original order', async () => {
    const getPage = vi
      .fn()
      .mockResolvedValueOnce(page([{ id: 1 }], 1, 3))
      .mockResolvedValueOnce(page([{ id: 2 }], 2, 3))
      .mockResolvedValueOnce(page([{ id: 3 }], 3, 3));

    expect(await fetchAllPages(getPage)).toEqual([{ id: 1 }, { id: 2 }, { id: 3 }]);
    expect(getPage.mock.calls.map((c) => c[0])).toEqual([1, 2, 3]);
  });

  it('returns an empty array for an empty result set without fetching a second page', async () => {
    const getPage = vi.fn().mockResolvedValueOnce(page([], 1, 0));
    expect(await fetchAllPages(getPage)).toEqual([]);
    expect(getPage).toHaveBeenCalledTimes(1);
  });
});
