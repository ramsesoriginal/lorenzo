import { afterEach, beforeEach, expect, it, vi } from 'vitest';

vi.mock('../../src/lib/auth', () => ({
  getAccessToken: vi.fn(async (): Promise<string | undefined> => 'token'),
}));

import { getAccessToken } from '../../src/lib/auth';
import { unlinkCharacterFromPlayer } from '../../src/lib/characters';
import { getMe } from '../../src/lib/me';
import { deleteProfilePicture, uploadProfilePicture } from '../../src/lib/profile';
import {
  getTenant,
  removePlayer,
  updateTenant,
  uploadCampaignPicture,
  uploadTenantPicture,
} from '../../src/lib/tenants';

const fetchMock = vi.hoisted(() => {
  const mock = vi.fn<typeof fetch>();
  vi.stubGlobal('fetch', mock);
  return mock;
});
vi.mock('../../src/lib/config', () => ({ API_BASE_URL: 'http://api.test' }));
beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  vi.mocked(getAccessToken).mockResolvedValue('token');
});
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

it('does not send a request without a session', async () => {
  vi.mocked(getAccessToken).mockResolvedValueOnce(undefined);
  await expect(getMe()).rejects.toMatchObject({ status: 401 });
  expect(fetchMock).not.toHaveBeenCalled();
});

it('accepts an empty successful delete response', async () => {
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
  await expect(deleteProfilePicture()).resolves.toBeUndefined();
});

it.each([
  ['/me/picture', uploadProfilePicture],
  ['/tenants/t/picture', (file: File) => uploadTenantPicture('t', file)],
  ['/tenants/t/campaigns/c/picture', (file: File) => uploadCampaignPicture('t', 'c', file)],
])('sends actual multipart bytes to %s', async (path, upload) => {
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
  await upload(new File(['picture bytes'], 'portrait.png', { type: 'image/png' }));
  const request = fetchMock.mock.calls[0][0] as Request;
  expect(new URL(request.url).pathname).toBe(path);
  expect(request.headers.get('Content-Type')).toContain('multipart/form-data; boundary=');
  const file = (await request.formData()).get('file') as File;
  expect(file.name).toBe('portrait.png');
  expect(await file.text()).toBe('picture bytes');
});

it('uses the version read before editing and sends only the slug', async () => {
  fetchMock.mockResolvedValueOnce(
    Response.json({ id: 'tenant', slug: 'old' }, { headers: { ETag: 'version-1' } }),
  );
  const { tenant, etag } = await getTenant('tenant');
  fetchMock.mockResolvedValueOnce(Response.json({ detail: 'Changed meanwhile' }, { status: 412 }));
  await expect(updateTenant(tenant.id, { slug: 'new' }, etag)).rejects.toMatchObject({
    status: 412,
  });
  const request = fetchMock.mock.calls[1][0] as Request;
  expect(request.headers.get('If-Match')).toBe('version-1');
  expect(await request.json()).toEqual({ slug: 'new' });
});

it('refuses to open an editor without a version', async () => {
  fetchMock.mockResolvedValueOnce(Response.json({ id: 'tenant' }));
  await expect(getTenant('tenant')).rejects.toThrow('Tenant editing is temporarily unavailable');
});

it('sends only the fields that changed when a library is edited', async () => {
  fetchMock.mockResolvedValueOnce(Response.json({ id: 'tenant', name: 'New name' }));
  await updateTenant('tenant', { name: 'New name', description: '' }, 'version-2');
  const request = fetchMock.mock.calls[0][0] as Request;
  expect(request.method).toBe('PATCH');
  expect(request.headers.get('If-Match')).toBe('version-2');
  expect(await request.json()).toEqual({ name: 'New name', description: '' });
});

it('removes a player, and unlinks a character from one, with one DELETE each', async () => {
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
  await removePlayer('t', 'c', 'p');
  fetchMock.mockResolvedValueOnce(Response.json({ entity_id: 'e', name: 'Cael', players: [] }));
  await unlinkCharacterFromPlayer('t', 'e', 'p');
  const [first, second] = fetchMock.mock.calls.map(([request]) => request as Request);
  expect([first.method, new URL(first.url).pathname]).toEqual([
    'DELETE',
    '/tenants/t/campaigns/c/players/p',
  ]);
  expect([second.method, new URL(second.url).pathname]).toEqual([
    'DELETE',
    '/tenants/t/characters/e/players/p',
  ]);
});
