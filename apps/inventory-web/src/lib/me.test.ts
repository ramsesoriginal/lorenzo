import { beforeEach, describe, expect, it, vi } from 'vitest';

// An API holding one viewer and the campaigns of whichever tenant is asked about.
const api = vi.hoisted(() => ({
  me: {
    campaign_gm_grants: [] as { id: string }[],
    memberships: [] as { tenant_id: string; role: string }[],
    players: [] as { tenant_id: string; self_service_effective: boolean }[],
  },
  campaigns: {} as Record<string, { id: string }[]>,
  characters: [] as { entity_id: string; name: string; is_pc: boolean }[],
  GET: vi.fn(),
}));
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  client: { GET: api.GET },
}));

const page = <T>(items: T[]) => ({ items, total: items.length, page: 1, size: 100, pages: 1 });

beforeEach(() => {
  vi.resetModules();
  api.me = { campaign_gm_grants: [], memberships: [], players: [] };
  api.campaigns = {};
  api.characters = [];
  api.GET.mockReset().mockImplementation(async (path: string, options) => {
    const tenant = options?.params?.path?.tenant_id;
    const data =
      path === '/me'
        ? api.me
        : path.endsWith('/campaigns')
          ? page(api.campaigns[tenant] ?? [])
          : path.endsWith('/characters')
            ? page(api.characters)
            : page([]);
    return { data, response: new Response() };
  });
});

describe('isCampaignGm', () => {
  it('counts only grants for campaigns in the tenant asked about', async () => {
    const { isCampaignGm } = await import('./me');
    api.me.campaign_gm_grants = [{ id: 'elsewhere' }];
    api.campaigns = { here: [{ id: 'ours' }], there: [{ id: 'elsewhere' }] };
    expect(await isCampaignGm('here')).toBe(false);
    expect(await isCampaignGm('there')).toBe(true);
  });

  it("doesn't list campaigns for someone who GMs nothing", async () => {
    const { isCampaignGm } = await import('./me');
    expect(await isCampaignGm('here')).toBe(false);
    expect(api.GET).toHaveBeenCalledTimes(1);
  });
});

describe('seatsIn', () => {
  it("lists the viewer's own seats in the library asked about, with what self-service says", async () => {
    const { seatsIn } = await import('./me');
    api.me.players = [
      { tenant_id: 'here', self_service_effective: true },
      { tenant_id: 'there', self_service_effective: false },
    ];
    expect(await seatsIn('here')).toEqual([{ tenant_id: 'here', self_service_effective: true }]);
    expect(await seatsIn('nowhere')).toEqual([]);
  });
});

describe('listBeings', () => {
  it("searches the tenant's characters for someone without a membership", async () => {
    const { listBeings } = await import('./beings');
    api.characters = [
      { entity_id: 'a', name: 'Ashfang', is_pc: true },
      { entity_id: 'b', name: 'Brisk', is_pc: true },
    ];
    const found = await listBeings('here', 'bri');
    expect(found.items.map((being) => being.name)).toEqual(['Brisk']);
    expect(api.GET).not.toHaveBeenCalledWith('/tenants/{tenant_id}/beings', expect.anything());
  });

  it("searches the tenant's characters for an Author, who reaches no being", async () => {
    const { listBeings } = await import('./beings');
    api.me.memberships = [{ tenant_id: 'here', role: 'author' }];
    api.characters = [{ entity_id: 'a', name: 'Ashfang', is_pc: true }];
    const found = await listBeings('here', 'ash');
    expect(found.items.map((being) => being.name)).toEqual(['Ashfang']);
    expect(api.GET).not.toHaveBeenCalledWith('/tenants/{tenant_id}/beings', expect.anything());
  });

  it('searches every being for an Organizer', async () => {
    const { listBeings } = await import('./beings');
    api.me.memberships = [{ tenant_id: 'here', role: 'orga' }];
    await listBeings('here', 'bri');
    expect(api.GET).toHaveBeenCalledWith('/tenants/{tenant_id}/beings', {
      params: { path: { tenant_id: 'here' }, query: { q: 'bri' } },
    });
  });
});

describe('isTenantMember and isTenantAdmin', () => {
  it('count an Author as a member, who reads the catalog, and not as an administrator', async () => {
    const { isTenantAdmin, isTenantMember } = await import('./me');
    api.me.memberships = [
      { tenant_id: 'wrote', role: 'author' },
      { tenant_id: 'ran', role: 'orga' },
      { tenant_id: 'owned', role: 'owner' },
    ];
    expect(await isTenantMember('wrote')).toBe(true);
    expect(await isTenantAdmin('wrote')).toBe(false);
    expect(await isTenantAdmin('ran')).toBe(true);
    expect(await isTenantAdmin('owned')).toBe(true);
    expect(await isTenantMember('elsewhere')).toBe(false);
    expect(await isTenantAdmin('elsewhere')).toBe(false);
  });
});
