import { afterEach, beforeEach, expect, it, vi } from 'vitest';

vi.mock('../../src/lib/auth', () => ({
  getAccessToken: vi.fn(async (): Promise<string | undefined> => 'token'),
}));
vi.mock('../../src/lib/config', () => ({ API_BASE_URL: 'http://api.test' }));

import { getAccessToken } from '../../src/lib/auth';
import { clearCache } from '../../src/lib/cache';
import { coverUrl } from '../../src/lib/discoverApi';
import { fetchPictureUrl } from '../../src/lib/pictureFetch';
import { deleteTenantPicture, tenantPictureUrl, uploadTenantPicture } from '../../src/lib/tenants';

const fetchMock = vi.hoisted(() => {
  const mock = vi.fn<typeof fetch>();
  vi.stubGlobal('fetch', mock);
  return mock;
});

let made = 0;

beforeEach(() => {
  clearCache();
  made = 0;
  vi.stubGlobal('fetch', fetchMock);
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => `blob:picture-${++made}`);
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  vi.mocked(getAccessToken).mockResolvedValue('token');
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

const picture = () => new Response('png bytes', { headers: { 'Content-Type': 'image/png' } });

function sentTo(call: number): { url: string; authorization: string | null } {
  const [url, init] = fetchMock.mock.calls[call] as [string, RequestInit];

  return { url, authorization: new Headers(init.headers).get('Authorization') };
}

it('fetches a picture with the token and answers a blob address', async () => {
  fetchMock.mockResolvedValueOnce(picture());

  await expect(fetchPictureUrl('/tenants/t/picture')).resolves.toBe('blob:picture-1');
  expect(sentTo(0)).toEqual({
    url: 'http://api.test/tenants/t/picture',
    authorization: 'Bearer token',
  });
});

it('refuses with the API status, for the page to leave the picture out', async () => {
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 404 }));

  await expect(fetchPictureUrl('/tenants/t/picture')).rejects.toMatchObject({ status: 404 });
});

it('asks for a tenant picture once, and again after it is changed or removed', async () => {
  fetchMock.mockImplementation(async () => picture());

  const first = await tenantPictureUrl('t');

  expect(await tenantPictureUrl('t')).toBe(first);
  expect(fetchMock).toHaveBeenCalledTimes(1);

  fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
  await uploadTenantPicture('t', new File(['x'], 'p.png', { type: 'image/png' }));
  const second = await tenantPictureUrl('t');

  expect(second).not.toBe(first);

  fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
  await deleteTenantPicture('t');
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 404 }));
  await expect(tenantPictureUrl('t')).rejects.toMatchObject({ status: 404 });
  // A failure is not kept.
  fetchMock.mockResolvedValueOnce(picture());
  await expect(tenantPictureUrl('t')).resolves.toMatch(/^blob:/);
});

it('fetches a cover with the token too', async () => {
  fetchMock.mockResolvedValueOnce(picture());

  await coverUrl('r');

  expect(sentTo(0)).toEqual({
    url: 'http://api.test/repositories/r/profile/cover',
    authorization: 'Bearer token',
  });
});
