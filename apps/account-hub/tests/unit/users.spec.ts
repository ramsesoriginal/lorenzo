import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../src/lib/auth', () => ({ getAccessToken: vi.fn(async () => 'token') }));

import { findUserByEmail, findUserByNickname } from '../../src/lib/users';

const fetchMock = vi.hoisted(() => {
  const mock = vi.fn<typeof fetch>();
  vi.stubGlobal('fetch', mock);
  return mock;
});
vi.mock('../../src/lib/config', () => ({ API_BASE_URL: 'http://api.test' }));
beforeEach(() => vi.stubGlobal('fetch', fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe('exact-match user lookup through the shared client', () => {
  it('encodes email and attaches the token', async () => {
    const user = { id: 'u1', nickname: 'nick', display_name: 'Nick' };
    fetchMock.mockResolvedValueOnce(Response.json(user));
    await expect(findUserByEmail('a+b@example.com')).resolves.toEqual(user);
    const request = fetchMock.mock.calls[0][0] as Request;
    expect(request.url).toContain('/users/by-email/a%2Bb%40example.com');
    expect(request.headers.get('Authorization')).toBe('Bearer token');
  });
  it('returns null for an exact-match miss', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ detail: 'No user' }, { status: 404 }));
    await expect(findUserByEmail('missing@example.com')).resolves.toBeNull();
  });
  it('keeps other failures visible, using the API message', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ detail: 'Try again later' }, { status: 503 }));
    await expect(findUserByNickname('nick')).rejects.toThrow('Try again later');
  });
  it('encodes a nickname without changing it', async () => {
    fetchMock.mockResolvedValueOnce(
      Response.json({ id: 'u1', nickname: null, display_name: null }),
    );
    await findUserByNickname('a b');
    expect((fetchMock.mock.calls[0][0] as Request).url).toContain('/users/by-nickname/a%20b');
  });
});
