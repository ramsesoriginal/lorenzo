import { beforeEach, describe, expect, it, vi } from 'vitest';

// An API with the viewer's libraries, two pages of them, and one entity with a slug.
const api = vi.hoisted(() => ({ GET: vi.fn() }));
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  client: { GET: api.GET },
}));

import { addressedTenant, beingNamed, isId, tenantIdFor, tenantNamed } from './addresses';
import type { TenantSummary } from './types';

const VALE = '0b6f7c1e-3a52-4d8e-9f10-2c4b6a8d0e13';
const COAST = '5d2e9a40-7b61-4c3f-8e25-9a1b3c5d7f02';
const ASHFANG = '9e8d7c6b-5a49-4382-9170-6f5e4d3c2b1a';
const tenant = (id: string, slug: string): TenantSummary => ({
  id,
  slug,
  name: slug,
  role: 'participant',
  kind: 'play',
});
const PAGES = [[tenant(VALE, 'sunken-vale')], [tenant(COAST, 'storm-coast')]];

beforeEach(() => {
  api.GET.mockReset().mockImplementation(async (path, options) => {
    if (path === '/tenants') {
      const page = options.params.query.page as number;
      const data = { items: PAGES[page - 1], total: 2, page, size: 1, pages: 2 };
      return { data, response: new Response() };
    }
    const data = (options.params.query.slug as string[])
      .filter((slug) => slug === 'ashfang')
      .map((slug) => ({ slug, entity_id: ASHFANG, name: 'Ashfang', kinds: ['being'] }));
    return { data, response: new Response() };
  });
});

describe('isId', () => {
  it('takes a UUID, in either case, as an id', () => {
    expect(isId(VALE)).toBe(true);
    expect(isId(VALE.toUpperCase())).toBe(true);
  });

  it('takes anything else as a slug', () => {
    expect(isId('sunken-vale')).toBe(false);
    expect(isId(`${VALE}-2`)).toBe(false);
    expect(isId('')).toBe(false);
  });
});

describe('tenantNamed', () => {
  const tenants = PAGES.flat();

  it('finds a tenant by id or by slug', () => {
    expect(tenantNamed(tenants, COAST)?.slug).toBe('storm-coast');
    expect(tenantNamed(tenants, 'sunken-vale')?.id).toBe(VALE);
  });

  it("doesn't take an id for a slug, or a slug for a name", () => {
    expect(tenantNamed([tenant(VALE, COAST)], COAST)).toBeUndefined();
    expect(tenantNamed(tenants, 'Sunken-Vale')).toBeUndefined();
  });
});

describe('tenantIdFor', () => {
  it('takes an id as it is, without asking', async () => {
    expect(await tenantIdFor(VALE)).toBe(VALE);
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("finds a slug on any page of the viewer's libraries, and asks once", async () => {
    expect(await tenantIdFor('storm-coast')).toBe(COAST);
    expect(await tenantIdFor('storm-coast')).toBe(COAST);
    expect(api.GET.mock.calls.map(([, options]) => options.params.query.page)).toEqual([1, 2]);
  });

  it("is null for a slug none of the viewer's libraries has", async () => {
    expect(await tenantIdFor('elsewhere')).toBeNull();
  });
});

describe('addressedTenant', () => {
  it('says nothing when there is no tenant in the address', async () => {
    expect(await addressedTenant(null)).toEqual({ id: null, problem: null });
  });

  it('says which library it could not find', async () => {
    expect(await addressedTenant('nowhere')).toEqual({
      id: null,
      problem: "There's no library “nowhere” you can see.",
    });
    expect(await addressedTenant('sunken-vale')).toEqual({ id: VALE, problem: null });
  });

  it('says why a lookup failed', async () => {
    api.GET.mockResolvedValue({
      error: { detail: 'Down for maintenance.' },
      response: new Response(null, { status: 503 }),
    });
    expect((await addressedTenant('broken')).problem).toContain('Down for maintenance.');
  });
});

describe('beingNamed', () => {
  it('names an id by itself, without asking', async () => {
    expect(await beingNamed(VALE, ASHFANG)).toEqual({ entity_id: ASHFANG, name: ASHFANG });
    expect(api.GET).not.toHaveBeenCalled();
  });

  it('resolves a slug to what holds it, and is null for one nothing holds', async () => {
    expect(await beingNamed(VALE, 'ashfang')).toEqual({ entity_id: ASHFANG, name: 'Ashfang' });
    expect(await beingNamed(VALE, 'brisk')).toBeNull();
  });
});
