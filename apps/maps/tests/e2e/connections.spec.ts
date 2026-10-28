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

const PLANE = {
  format: 'lorenzo.map-system/1',
  kind: 'plane',
  extent: [0, 0, 1000, 800],
};

/** A library with a GM and a player. */
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
  const place = (name: string) =>
    ok(
      gm.POST('/tenants/{tenant_id}/locations', {
        params: { path },
        body: { name, is_public: true },
      }),
    );
  const makeMap = (name: string) =>
    ok(
      gm.POST('/tenants/{tenant_id}/maps', {
        params: { path },
        body: { name, system: PLANE, is_public: true },
      }),
    );
  const draw = (map: string, entry: string, at: number[]) =>
    ok(
      gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
        params: { path: { ...path, map_id: map, entry_id: entry } },
        body: {
          geometry: { format: 'lorenzo.geometry/1', parts: [{ shape: 'point', at }] },
          role: 'site',
          z: 0,
        },
      }),
    );
  const join = (end_a: string, end_b: string, name: string, one_way = false) =>
    ok(
      gm.POST('/tenants/{tenant_id}/connections', {
        params: { path },
        body: { name, end_a, end_b, one_way, prototypes: [], is_public: true },
      }),
    );
  const connections = async () =>
    (await ok(gm.GET('/tenants/{tenant_id}/connections', { params: { path } }))).items;
  return { subject, gm, tenant, playerSubject, path, place, makeMap, draw, join, connections };
}

const here = (tenant: string, id: string) => `/location/?tenant=${tenant}&id=${id}`;

test('a writer joins two Locations and each page says where it goes', async ({ browser }) => {
  const w = await world();
  const a = await w.place('Hollowmere');
  const b = await w.place('Dunmere');
  const c = await w.place('Brindle');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(here(w.tenant.id, a.id));
    await expect(page.getByRole('heading', { name: 'Hollowmere', exact: true })).toBeVisible();
    await expect(page.getByText('Nothing connects to this Location yet.')).toBeVisible();
    // Nothing is chosen yet.
    await page.getByRole('button', { name: 'Join', exact: true }).click();
    await expect(page.getByText('Choose the Location to join it to.')).toBeVisible();
    // A way both ways.
    await page.getByLabel('Join it to (type a name)').fill('Dun');
    await page.getByLabel('Locations to join it to').selectOption({ label: 'Dunmere' });
    await page.getByLabel('Called', { exact: true }).fill("King's Road");
    await page.getByRole('button', { name: 'Join', exact: true }).click();
    await expect(page.getByText("King's Road to")).toBeVisible();
    await expect(
      page.locator('.map-connections').getByRole('link', { name: 'Dunmere' }),
    ).toBeVisible();
    // A way one way only, leaving here.
    await page.getByLabel('Join it to (type a name)').fill('Brin');
    await page.getByLabel('Locations to join it to').selectOption({ label: 'Brindle' });
    await page.getByLabel('Called', { exact: true }).fill('Ferry');
    await page.getByLabel('One way only').check();
    await page.getByLabel('The way goes').selectOption('from');
    await page.getByRole('button', { name: 'Join', exact: true }).click();
    await expect(page.getByText('Ferry one way to')).toBeVisible();
    const made = await w.connections();
    expect(made.map((m) => [m.name, m.one_way, m.end_a.name, m.end_b.name])).toEqual([
      ['Ferry', true, 'Hollowmere', 'Brindle'],
      ["King's Road", false, 'Hollowmere', 'Dunmere'],
    ]);

    // The other end says it from its side: the ferry arrives at Brindle.
    await page.goto(here(w.tenant.id, c.id));
    await expect(page.getByText('Ferry one way from')).toBeVisible();
    await expect(
      page.locator('.map-connections').getByRole('link', { name: 'Hollowmere' }),
    ).toBeVisible();
    await page.goto(here(w.tenant.id, b.id));
    await expect(page.getByText("King's Road to")).toBeVisible();

    // Removing one asks twice.
    await page.goto(here(w.tenant.id, a.id));
    await page.getByRole('button', { name: "Remove King's Road" }).click();
    await expect(page.getByRole('button', { name: "Really remove King's Road?" })).toBeVisible();
    expect(await w.connections()).toHaveLength(2);
    await page.getByRole('button', { name: "Really remove King's Road?" }).click();
    await expect.poll(async () => (await w.connections()).map((m) => m.name)).toEqual(['Ferry']);
    await expect(page.getByText("King's Road to")).toHaveCount(0);
  } finally {
    await page.context().close();
  }
});

test('a Map says where a place leads, with the other Maps it is on', async ({ browser }) => {
  const w = await world();
  const west = await w.makeMap('Western Map');
  const east = await w.makeMap('Eastern Map');
  const gate = await w.place('Gate');
  const far = await w.place('Far bank');
  await w.draw(west.id, gate.id, [100, 100]);
  await w.draw(east.id, far.id, [200, 200]);
  await w.join(gate.id, far.id, 'Bridge');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${west.id}`);
    await expect(page.getByRole('heading', { name: 'Western Map', exact: true })).toBeVisible();
    await page.locator('.map-place', { hasText: 'Gate' }).click();
    const panel = page.locator('.map-panel');
    await expect(panel.getByRole('heading', { name: 'Leads to' })).toBeVisible();
    await expect(panel.getByText(/Bridge to Far bank/)).toBeVisible();
    await expect(panel.getByRole('link', { name: 'Eastern Map' })).toBeVisible();
    // A place with no connection says nothing of the kind.
    await w.draw(west.id, (await w.place('Hermitage')).id, [400, 400]);
    await page.reload();
    await page.locator('.map-place', { hasText: 'Hermitage' }).click();
    await expect(panel.getByRole('heading', { name: 'Leads to' })).toHaveCount(0);
  } finally {
    await page.context().close();
  }
});

test('a player reads connections and has no form to make them', async ({ browser }) => {
  const w = await world();
  const a = await w.place('Hollowmere');
  const b = await w.place('Dunmere');
  await w.join(a.id, b.id, "King's Road");
  const page = await signedIn(browser, w.playerSubject);
  try {
    await page.goto(here(w.tenant.id, a.id));
    await expect(page.getByRole('heading', { name: 'Hollowmere', exact: true })).toBeVisible();
    await expect(page.getByText("King's Road to")).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Join to another place' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /^Remove/ })).toHaveCount(0);
  } finally {
    await page.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`the Connections section and a place's panel have no accessibility errors in ${theme}`, async ({
    browser,
  }) => {
    const w = await world();
    const west = await w.makeMap('Western Map');
    const a = await w.place('Hollowmere');
    const b = await w.place('Dunmere');
    await w.draw(west.id, a.id, [100, 100]);
    await w.join(a.id, b.id, "King's Road");
    const page = await signedIn(browser, w.subject, theme);
    try {
      await page.goto(here(w.tenant.id, a.id));
      await expect(page.getByText("King's Road to")).toBeVisible();
      const section = await new AxeBuilder({ page }).analyze();
      expect(section.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.goto(`/map/?tenant=${w.tenant.id}&id=${west.id}`);
      await page.locator('.map-place', { hasText: 'Hollowmere' }).click();
      await expect(page.getByRole('heading', { name: 'Leads to' })).toBeVisible();
      const panel = await new AxeBuilder({ page }).analyze();
      expect(panel.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}
