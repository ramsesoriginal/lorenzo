import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { type Browser, expect, test } from '@playwright/test';
import { apiAs, ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';

async function signedIn(browser: Browser, subject: string, theme?: 'light' | 'dark') {
  const token = await refreshTokenFor(subject);
  const localStorage = [{ name: REFRESH_TOKEN_KEY, value: token }];
  if (theme) localStorage.push({ name: 'lorenzo:maps:theme', value: theme });
  const context = await browser.newContext({
    storageState: { cookies: [], origins: [{ origin: SITE_URL, localStorage }] },
  });
  return context.newPage();
}

const SYSTEM = { format: 'lorenzo.map-system/1', kind: 'plane', extent: [0, 0, 1000, 800] };
const geometry = (...parts: Record<string, unknown>[]) => ({ format: 'lorenzo.geometry/1', parts });

/** A library with a GM and a player, and a Map with a pin, a region, a route and a person. */
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
  const place = (name: string, isPublic = true) =>
    ok(
      gm.POST('/tenants/{tenant_id}/locations', {
        params: { path },
        body: { name, is_public: isPublic },
      }),
    );
  const chart = await ok(
    gm.POST('/tenants/{tenant_id}/maps', {
      params: { path },
      body: { name: 'Sword Coast', slug: 'coast', system: SYSTEM, is_public: true },
    }),
  );
  const draw = (
    entry: string,
    shape: Record<string, unknown>,
    extra: { role?: string; z?: number } = {},
  ) =>
    ok(
      gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
        params: { path: { ...path, map_id: chart.id, entry_id: entry } },
        body: { geometry: shape, z: 0, ...extra },
      }),
    );
  const harbour = await place('Harbour town');
  const marsh = await place('Wet marsh');
  const road = await place('Salt road');
  const hidden = await place('Secret vault', false);
  const bram = await ok(
    gm.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Bram the guide', kinds: ['being'], parents: [] },
    }),
  );
  await draw(harbour.id, geometry({ shape: 'point', at: [300, 300] }), { role: 'site' });
  await draw(
    marsh.id,
    geometry({
      shape: 'polygon',
      rings: [
        [
          [500, 400],
          [800, 400],
          [800, 700],
          [500, 700],
        ],
      ],
    }),
    { role: 'territory' },
  );
  await draw(
    road.id,
    geometry({
      shape: 'polyline',
      pts: [
        [300, 300],
        [650, 550],
      ],
    }),
    { role: 'route' },
  );
  await draw(bram.id, geometry({ shape: 'point', at: [300, 430] }), { role: 'presence', z: 2 });
  await draw(hidden.id, geometry({ shape: 'point', at: [900, 100] }), { role: 'site' });
  return { subject, gm, tenant, player, playerSubject, path, chart, draw, place };
}

test('a GM sees the Map drawn, and the toggles, zoom and selection work', async ({ browser }) => {
  const w = await world();
  const gm = await signedIn(browser, w.subject);
  try {
    await gm.goto(`/map/?tenant=${w.tenant.id}&slug=coast`);
    await expect(gm.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    const drawing = gm.getByRole('group', { name: 'Map of Sword Coast' });
    await expect(drawing).toBeVisible();
    // Every placement the GM may see is on the list, the hidden one included for a GM.
    const list = gm.locator('.map-places');
    await expect(list.getByRole('button')).toHaveCount(5);
    // Marks: the pin, the region, the route and the person are drawn.
    for (const name of ['Harbour town', 'Wet marsh', 'Salt road', 'Bram the guide']) {
      await expect(drawing.locator(`[aria-label^="${name}"]`)).toHaveCount(1);
    }
    // The toggles hide and show their groups.
    await gm.getByLabel('Roads', { exact: true }).uncheck();
    await expect(drawing.locator('[aria-label^="Salt road"]')).toHaveCount(0);
    await gm.getByLabel('Roads', { exact: true }).check();
    await expect(drawing.locator('[aria-label^="Salt road"]')).toHaveCount(1);
    await gm.getByLabel('People', { exact: true }).uncheck();
    await expect(drawing.locator('[aria-label^="Bram the guide"]')).toHaveCount(0);
    await gm.getByLabel('People', { exact: true }).check();
    await gm.getByLabel('Places', { exact: true }).uncheck();
    await expect(drawing.locator('[aria-label^="Harbour town"]')).toHaveCount(0);
    await gm.getByLabel('Places', { exact: true }).check();
    // Zoom and "Whole map".
    await expect(gm.getByText('100%', { exact: true })).toBeVisible();
    await gm.getByRole('button', { name: 'Zoom in' }).click();
    await expect(gm.getByText('100%', { exact: true })).toHaveCount(0);
    await gm.getByRole('button', { name: 'Whole map' }).click();
    await expect(gm.getByText('100%', { exact: true })).toBeVisible();
    // Selecting from the list and from the drawing agree.
    await list.getByRole('button', { name: /Wet marsh/ }).click();
    await expect(list.getByRole('button', { name: /Wet marsh/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await expect(gm.getByRole('link', { name: 'Wet marsh', exact: true })).toBeVisible();
    await expect(gm.getByRole('button', { name: 'Centre on Wet marsh' })).toBeVisible();
    await drawing.locator('[aria-label^="Harbour town"] .m-pinbg').click();
    await expect(list.getByRole('button', { name: /Harbour town/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await expect(list.getByRole('button', { name: /Wet marsh/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    await gm.keyboard.press('Escape');
    await expect(gm.getByText('Select a place on the map or in the list.')).toBeVisible();
  } finally {
    await gm.context().close();
  }
});

test('a player sees only what they may, and a hidden Map reads like a missing one', async ({
  browser,
}) => {
  const w = await world();
  const player = await signedIn(browser, w.playerSubject);
  try {
    await player.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(player.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await expect(player.locator('.map-places').getByRole('button')).toHaveCount(4);
    await expect(player.getByText('Secret vault')).toHaveCount(0);
    await expect(player.getByText('Visible to everyone')).toHaveCount(0);
    // A restricted Map and a missing one say the same.
    const secret = await ok(
      w.gm.POST('/tenants/{tenant_id}/maps', {
        params: { path: w.path },
        body: { name: 'Hidden chart', system: SYSTEM, is_public: false },
      }),
    );
    const words: string[] = [];
    for (const id of [secret.id, randomUUID()]) {
      await player.goto(`/map/?tenant=${w.tenant.id}&id=${id}`);
      const notice = player.getByRole('alert');
      await expect(notice).toBeVisible();
      words.push((await notice.textContent()) ?? '');
    }
    expect(words[0]).toBe(words[1]);
    await player.goto(`/maps/?tenant=${w.tenant.id}`);
    await expect(player.getByRole('link', { name: 'Sword Coast', exact: true })).toBeVisible();
    await expect(player.getByText('Hidden chart')).toHaveCount(0);
  } finally {
    await player.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`the Map pages have no accessibility errors in ${theme}`, async ({ browser }) => {
    const w = await world();
    const gm = await signedIn(browser, w.subject, theme);
    try {
      for (const address of [
        `/maps/?tenant=${w.tenant.id}`,
        `/map/?tenant=${w.tenant.id}&id=${w.chart.id}`,
      ]) {
        await gm.goto(address);
        await expect(gm.locator('[data-page]')).toBeVisible();
        await expect(gm.locator('[data-loading]')).toHaveCount(0);
        await expect(gm.getByRole('heading', { level: 1 })).toBeVisible();
        const result = await new AxeBuilder({ page: gm }).analyze();
        expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      }
    } finally {
      await gm.context().close();
    }
  });
}
