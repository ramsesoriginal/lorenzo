import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/lib/apiError';
import { readLibrary } from '../../src/lib/libraryData';
import * as tenants from '../../src/lib/tenants';
import type { CampaignSummaryOut, MeOut, TenantSummaryOut } from '../../src/lib/types';

vi.mock('../../src/lib/tenants', () => ({
  getCampaign: vi.fn(),
  getTenant: vi.fn(),
  listActivityLog: vi.fn(),
  listCampaignGms: vi.fn(),
  listCampaignPlayers: vi.fn(),
  listTenantCampaigns: vi.fn(),
  listTenantRoster: vi.fn(),
}));

const library: TenantSummaryOut = {
  id: 'library',
  name: 'Library',
  slug: 'library',
  kind: 'play',
  role: 'participant',
};
const played: CampaignSummaryOut = {
  id: 'played',
  name: 'My table',
  slug: 'played',
  game_system: 'test',
  secret: false,
};
const other: CampaignSummaryOut = { ...played, id: 'other', name: 'Another table', slug: 'other' };
const page = <T>(items: T[]) => ({ items, total: items.length, page: 1, size: 50, pages: 1 });
const me: MeOut = {
  id: 'player',
  authgear_subject_id: 'player',
  email: null,
  nickname: null,
  display_name: null,
  pronouns: null,
  bio: null,
  locales: [],
  user_color: null,
  picture_url: 'https://example.com/picture',
  memberships: [],
  campaign_gm_grants: [],
  players: [
    {
      id: 'seat',
      tenant_id: library.id,
      campaign_id: played.id,
      characters: [],
      self_service_effective: true,
    },
  ],
  capabilities: { create_tenant: false },
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(tenants.listTenantCampaigns).mockResolvedValue(page([played, other]));
  vi.mocked(tenants.getTenant).mockResolvedValue({
    tenant: {
      id: library.id,
      name: library.name,
      slug: library.slug,
      kind: 'play',
      published_at: null,
      description: 'Library description',
      npcs_shared_with_gms: true,
      created_by: null,
      updated_by: null,
    },
    etag: 'version',
  });
  vi.mocked(tenants.listTenantRoster).mockResolvedValue(page([]));
  vi.mocked(tenants.listActivityLog).mockResolvedValue(page([]));
  vi.mocked(tenants.listCampaignGms).mockResolvedValue([]);
  vi.mocked(tenants.listCampaignPlayers).mockResolvedValue(page([]));
  vi.mocked(tenants.getCampaign).mockImplementation(async (_tenantId, id) => ({
    ...(id === played.id ? played : other),
    tenant_id: library.id,
    description: `${id} description`,
    player_self_service: true,
    created_by: null,
    updated_by: null,
    created_at: '2026-10-09T00:00:00Z',
    updated_at: '2026-10-09T00:00:00Z',
  }));
});

describe('library campaign reads', () => {
  it('keeps other public campaigns in the catalog without requesting their details', async () => {
    const result = await readLibrary(library, me);
    expect(result.campaigns).toEqual([played, other]);
    expect(result.descriptions).toEqual(new Map([[played.id, 'played description']]));
    expect(tenants.getCampaign).toHaveBeenCalledExactlyOnceWith(library.id, played.id);
    expect(tenants.listTenantRoster).not.toHaveBeenCalled();
    expect(tenants.listCampaignPlayers).not.toHaveBeenCalled();
    expect(tenants.listCampaignGms).not.toHaveBeenCalled();
  });

  it('reads a GM campaign without a player seat or library membership', async () => {
    const result = await readLibrary(library, { ...me, players: [], campaign_gm_grants: [other] });
    expect(result.descriptions).toEqual(new Map([[other.id, 'other description']]));
    expect(tenants.getCampaign).toHaveBeenCalledExactlyOnceWith(library.id, other.id);
    expect(tenants.listCampaignPlayers).toHaveBeenCalledExactlyOnceWith(library.id, other.id);
  });

  it.each(['owner', 'orga'] as const)(
    'still reads all campaign descriptions for %s',
    async (role) => {
      const result = await readLibrary({ ...library, role }, me);
      expect(result.descriptions.size).toBe(2);
      expect(tenants.getCampaign).toHaveBeenCalledTimes(2);
      expect(tenants.listTenantRoster).toHaveBeenCalledExactlyOnceWith(library.id);
    },
  );

  it('keeps the library when a campaign detail is no longer accessible', async () => {
    vi.mocked(tenants.getCampaign).mockRejectedValue(new ApiError('No campaign', 404));
    const result = await readLibrary(library, me);
    expect(result.campaigns).toEqual([played, other]);
    expect(result.description).toBe('Library description');
    expect(result.descriptions.size).toBe(0);
  });

  it.each([
    new ApiError('Forbidden', 403),
    new ApiError('Server error', 500),
    new TypeError('Failed to fetch'),
  ])('surfaces other detail failures: %s', async (error) => {
    vi.mocked(tenants.getCampaign).mockRejectedValue(error);
    await expect(readLibrary(library, me)).rejects.toBe(error);
  });
});
