import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('@lorenzo/api-client', () => ({ getAppLinks: vi.fn() }));
vi.mock('./config', () => ({ API_BASE_URL: 'https://api.example' }));

import { getAppLinks } from '@lorenzo/api-client';
import { notificationsUrl } from './appLinks';

const registry = (links: Record<string, string>) =>
  ({ apps: {}, links }) as unknown as Awaited<ReturnType<typeof getAppLinks>>;

describe('notificationsUrl', () => {
  afterEach(() => vi.mocked(getAppLinks).mockReset());

  it("takes the registry's notifications link", async () => {
    vi.mocked(getAppLinks).mockResolvedValue(
      registry({ notifications: 'https://hub.live/notifications/' }),
    );
    expect(await notificationsUrl('https://hub.fallback')).toBe('https://hub.live/notifications/');
  });

  it("falls back to the build's own hub address when the registry lacks the entry", async () => {
    vi.mocked(getAppLinks).mockResolvedValue(registry({}));
    expect(await notificationsUrl('https://hub.fallback/')).toBe(
      'https://hub.fallback/notifications/',
    );
  });

  it('falls back when the registry cannot be reached', async () => {
    vi.mocked(getAppLinks).mockRejectedValue(new Error('offline'));
    expect(await notificationsUrl('https://hub.fallback')).toBe(
      'https://hub.fallback/notifications/',
    );
  });
});
