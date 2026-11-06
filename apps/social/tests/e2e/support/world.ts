// A library with people in it, and a browser that starts out signed in as one of them.
import { randomUUID } from 'node:crypto';
import type { Browser } from '@playwright/test';
import { apiAs, ok, refreshTokenFor } from './api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './env.ts';

export async function signedIn(browser: Browser, subject: string, theme?: 'light' | 'dark') {
  const token = await refreshTokenFor(subject);
  const localStorage = [{ name: REFRESH_TOKEN_KEY, value: token }];
  if (theme) localStorage.push({ name: 'lorenzo:social:theme', value: theme });
  const context = await browser.newContext({
    storageState: { cookies: [], origins: [{ origin: SITE_URL, localStorage }] },
  });
  return context.newPage();
}

/** A library with a GM and a player in one campaign, and a few places to tie together. */
export async function world() {
  const subject = `social-gm-${randomUUID()}`;
  const gm = await apiAs(subject, ['tenant_creator']);
  const me = await ok(gm.GET('/me'));
  const tenant = await ok(
    gm.POST('/tenants', { body: { name: `Social library ${randomUUID()}` } }),
  );
  const path = { tenant_id: tenant.id };
  const campaign = await ok(
    gm.POST('/tenants/{tenant_id}/campaigns', {
      params: { path },
      body: {
        name: 'Court campaign',
        game_system: 'Homebrew',
        slug: `court-${randomUUID()}`,
        description: '',
        secret: false,
      },
    }),
  );
  await ok(
    gm.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { ...path, campaign_id: campaign.id, user_id: me.id } },
    }),
  );
  const playerSubject = `social-player-${randomUUID()}`;
  const player = await apiAs(playerSubject);
  const playerMe = await ok(player.GET('/me'));
  await ok(
    gm.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { ...path, campaign_id: campaign.id } },
      body: { user_id: playerMe.id },
    }),
  );
  const entry = (name: string, isPublic = true) =>
    ok(
      gm.POST('/tenants/{tenant_id}/locations', {
        params: { path },
        body: { name, is_public: isPublic },
      }),
    );
  const tie = (name: string, a: string, b: string, isPublic: boolean) =>
    ok(
      gm.POST('/tenants/{tenant_id}/relationships', {
        params: { path },
        body: { name, end_a: a, end_b: b, one_way: false, is_public: isPublic },
      }),
    );
  return { tenant, path, gm, subject, playerSubject, entry, tie };
}

/** A numeric stat for a standing, on a scale, in a group of its own. */
export async function standing(
  w: Awaited<ReturnType<typeof world>>,
  name: string,
  scale: { min?: number; max?: number } = {},
) {
  const group = await ok(
    w.gm.POST('/tenants/{tenant_id}/stat-groups', {
      params: { path: w.path },
      body: { name: `${name} group`, priority: 0, mandatory: false },
    }),
  );
  return ok(
    w.gm.POST('/tenants/{tenant_id}/stat-definitions', {
      params: { path: w.path },
      body: {
        name,
        stat_group_id: group.id,
        value_type: 'int',
        adjustable_in_play: false,
        pin: false,
        signed: false,
        ...(scale.min === undefined ? {} : { min_value: scale.min }),
        ...(scale.max === undefined ? {} : { max_value: scale.max }),
      },
    }),
  );
}
