import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { type Browser, expect, test } from '@playwright/test';
import { apiAs, ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';

async function signedIn(browser: Browser, subject: string) {
  const token = await refreshTokenFor(subject);
  const context = await browser.newContext({
    storageState: {
      cookies: [],
      origins: [{ origin: SITE_URL, localStorage: [{ name: REFRESH_TOKEN_KEY, value: token }] }],
    },
  });
  return context.newPage();
}

const SYSTEM = { format: 'lorenzo.map-system/1', kind: 'plane', extent: [0, 0, 1000, 800] };
const POINT = {
  format: 'lorenzo.geometry/1',
  parts: [{ shape: 'point', at: [100, 100] }],
};

/** A library with a GM and a player, a Location drawn on an open Map and on a closed one. */
async function world() {
  const subject = `maps-gm-${randomUUID()}`;
  const gm = await apiAs(subject, ['tenant_creator']);
  const me = await ok(gm.GET('/me'));
  const tenant = await ok(gm.POST('/tenants', { body: { name: `Maps library ${randomUUID()}` } }));
  const path = { tenant_id: tenant.id };
  const campaign = await ok(
    gm.POST('/tenants/{tenant_id}/campaigns', {
      params: { path },
      body: {
        name: 'Harbour campaign',
        game_system: 'Homebrew',
        slug: `harbour-${randomUUID()}`,
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
  const playerSubject = `maps-player-${randomUUID()}`;
  const player = await apiAs(playerSubject);
  const playerMe = await ok(player.GET('/me'));
  await ok(
    gm.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { ...path, campaign_id: campaign.id } },
      body: { user_id: playerMe.id },
    }),
  );
  const quay = await ok(
    gm.POST('/tenants/{tenant_id}/locations', {
      params: { path },
      body: { name: 'The quay', is_public: true },
    }),
  );
  const open = await ok(
    gm.POST('/tenants/{tenant_id}/maps', {
      params: { path },
      body: { name: 'Sword Coast', system: SYSTEM, is_public: true },
    }),
  );
  const closed = await ok(
    gm.POST('/tenants/{tenant_id}/maps', {
      params: { path },
      body: { name: 'Secret chart', system: SYSTEM, is_public: false },
    }),
  );
  for (const chart of [open, closed]) {
    await ok(
      gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
        params: { path: { ...path, map_id: chart.id, entry_id: quay.id } },
        body: { geometry: POINT, z: 0 },
      }),
    );
  }
  await ok(
    gm.POST('/tenants/{tenant_id}/characters', {
      params: { path },
      body: { name: 'Bram', player_ids: [] },
    }),
  );
  return { subject, playerSubject, tenant, quay };
}

test('a row says on how many Maps it is drawn, and its page says which and where each character would say it is', async ({
  browser,
}) => {
  const w = await world();
  const gm = await signedIn(browser, w.subject);
  const player = await signedIn(browser, w.playerSubject);
  try {
    // The count is of the Maps this reader may see: two for the GM, one for the player.
    await gm.goto(`/locations/?tenant=${w.tenant.id}`);
    await expect(
      gm.locator('.place-row', { hasText: 'The quay' }).getByText('2 Maps'),
    ).toBeVisible();
    await player.goto(`/locations/?tenant=${w.tenant.id}`);
    await expect(
      player.locator('.place-row', { hasText: 'The quay' }).getByText('1 Map', { exact: true }),
    ).toBeVisible();

    // On these Maps: the Maps, as links, and for the player no trace of the closed one.
    await player.goto(`/location/?tenant=${w.tenant.id}&id=${w.quay.id}`);
    const onMaps = player.locator('section', {
      has: player.getByRole('heading', { name: 'On these Maps' }),
    });
    await expect(onMaps.getByRole('link', { name: 'Sword Coast' })).toBeVisible();
    await expect(player.getByText('Secret chart')).toHaveCount(0);
    // Where is…: a player has no character to ask for, and is told so.
    await expect(player.getByText('There is no character here to ask.')).toBeVisible();

    await gm.goto(`/location/?tenant=${w.tenant.id}&id=${w.quay.id}`);
    const gmMaps = gm.locator('section', {
      has: gm.getByRole('heading', { name: 'On these Maps' }),
    });
    await expect(gmMaps.getByRole('link', { name: 'Secret chart' })).toBeVisible();
    await expect(gmMaps.getByRole('link', { name: 'Sword Coast' })).toBeVisible();
    const where = gm.locator('section', { has: gm.getByRole('heading', { name: 'Where is…' }) });
    await expect(where.getByText('Bram')).toBeVisible();
    await expect(where.getByText('close by')).toBeVisible();
    const result = await new AxeBuilder({ page: gm }).exclude('.shell-bottom').analyze();
    expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);

    // A link goes to the Map.
    await gmMaps.getByRole('link', { name: 'Sword Coast' }).click();
    await expect(gm.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
  } finally {
    await gm.context().close();
    await player.context().close();
  }
});
