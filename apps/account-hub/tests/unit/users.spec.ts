import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/lib/apiError';

// Fully mocked, not `vi.importActual`-spread - api.ts imports auth.ts
// imports @authgear/web, which touches `window` on import (see format.ts's
// own comment on the same issue) and breaks under plain Vitest/Node;
// importActual would still trigger that real import just to spread it.
// apiFetch is the only export users.ts needs, so a full mock needs nothing
// real from api.ts at all.
vi.mock('../../src/lib/api', () => ({ apiFetch: vi.fn() }));

import { apiFetch } from '../../src/lib/api';
import { findUserByEmail, findUserByNickname } from '../../src/lib/users';

const mockedApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockedApiFetch.mockReset();
});

describe('findUserByEmail', () => {
  it('returns the user on success', async () => {
    const user = { id: 'u1', nickname: 'nick', display_name: 'Nick' };
    mockedApiFetch.mockResolvedValueOnce(user);
    await expect(findUserByEmail('a@b.com')).resolves.toEqual(user);
    expect(mockedApiFetch).toHaveBeenCalledWith('/users/by-email/a%40b.com');
  });

  it('returns null on a 404', async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError(404, '404 Not Found'));
    await expect(findUserByEmail('missing@example.com')).resolves.toBeNull();
  });

  it('rethrows any other error', async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError(500, '500 Server Error'));
    await expect(findUserByEmail('a@b.com')).rejects.toThrow('500 Server Error');
  });
});

describe('findUserByNickname', () => {
  it('returns null on a 404', async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError(404, '404 Not Found'));
    await expect(findUserByNickname('ghost')).resolves.toBeNull();
  });

  it('URL-encodes the nickname', async () => {
    mockedApiFetch.mockResolvedValueOnce({ id: 'u1', nickname: null, display_name: null });
    await findUserByNickname('a b');
    expect(mockedApiFetch).toHaveBeenCalledWith('/users/by-nickname/a%20b');
  });
});
