import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { type Browser, expect, type Page, test } from '@playwright/test';
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

/** A library with a GM and a player, a public Map with nothing on it, and a few Locations. */
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
  const chart = await ok(
    gm.POST('/tenants/{tenant_id}/maps', {
      params: { path },
      body: { name: 'Sword Coast', system: SYSTEM, is_public: true },
    }),
  );
  const place = (name: string, parent?: string) =>
    ok(
      gm.POST('/tenants/{tenant_id}/locations', {
        params: { path },
        body: { name, is_public: true, ...(parent ? { parent_id: parent } : {}) },
      }),
    );
  const read = async () =>
    (
      await ok(
        gm.GET('/tenants/{tenant_id}/maps/{map_id}/placements', {
          params: { path: { ...path, map_id: chart.id } },
        }),
      )
    ).items;
  return { subject, gm, tenant, player, playerSubject, path, chart, place, read };
}

type Geometry = {
  parts: { shape: string; at?: number[]; pts?: number[][]; rings?: number[][][] }[];
};

const geometryOf = (row: { geometry: unknown } | undefined): Geometry =>
  (row?.geometry ?? { parts: [] }) as Geometry;

/** A click at a fraction of the drawing, inside the sheet. */
async function clickSheet(page: Page, fx: number, fy: number) {
  const box = await page.locator('.map-stage').boundingBox();
  if (!box) throw new Error('the map has no box');
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
}

test('a writer makes a Map, draws, changes and undoes', async ({ browser }) => {
  const w = await world();
  const harbour = await w.place('Harbour');
  const page = await signedIn(browser, w.subject);
  try {
    // Make a Map from the library's list; a player is not offered the form.
    await page.goto(`/maps/?tenant=${w.tenant.id}`);
    await page.getByLabel('Name', { exact: true }).fill('Frostmarch');
    await page.getByLabel('Width', { exact: true }).fill('500');
    await page.getByLabel('Height', { exact: true }).fill('400');
    await page.getByRole('button', { name: 'Make the Map' }).click();
    await expect(page.getByRole('heading', { name: 'Frostmarch', exact: true })).toBeVisible();
    // Back to the Map the world made.
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();

    // A pin for an entry found by name.
    await page.getByRole('button', { name: 'Pin', exact: true }).click();
    await page.getByLabel('Find an entry by name').fill('Harbo');
    await page
      .locator('.map-edit-panel')
      .getByRole('button', { name: /^Harbour location$/ })
      .click();
    await expect(page.getByText('Click the map to place it.')).toBeVisible();
    await clickSheet(page, 0.3, 0.4);
    await expect(
      page.locator('.map-places').getByRole('button', { name: /Harbour/ }),
    ).toBeVisible();
    let rows = await w.read();
    expect(rows.map((r) => [r.name, r.role])).toEqual([['Harbour', 'site']]);
    expect(geometryOf(rows[0]).parts[0]?.shape).toBe('point');

    // An area for a new Location: four clicks and Enter.
    await page.getByRole('button', { name: 'Area', exact: true }).click();
    await page.getByLabel('Or make a new Location, named').fill('Old Town');
    await page.getByRole('button', { name: 'Draw a new Location' }).click();
    for (const [x, y] of [
      [0.5, 0.2],
      [0.8, 0.2],
      [0.8, 0.6],
      [0.5, 0.6],
    ] as const) {
      await clickSheet(page, x, y);
    }
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Change Old Town' })).toBeVisible();
    rows = await w.read();
    const town = rows.find((r) => r.name === 'Old Town');
    expect(town?.kinds).toEqual(['location']);
    expect(geometryOf(town).parts[0]?.rings?.[0]).toHaveLength(4);

    // What the API holds of the town, read again each time it is waited for.
    const town$ = async () => geometryOf((await w.read()).find((r) => r.name === 'Old Town'));
    const corner = async (i: number) => (await town$()).parts[0]?.rings?.[0]?.[i]?.[0];

    // A role, by the panel.
    await page.getByRole('combobox', { name: 'Role', exact: true }).selectOption('built-up');
    await expect
      .poll(async () => (await w.read()).find((r) => r.name === 'Old Town')?.role)
      .toBe('built-up');
    // A point, by number.
    await page.getByRole('group', { name: 'Point 1' }).getByLabel('x').fill('420');
    await page.getByRole('group', { name: 'Point 1' }).getByLabel('x').press('Tab');
    await expect.poll(() => corner(0)).toBe(420);

    // A handle, by drag.
    const beforeDrag = await corner(2);
    const handle = page.locator('.m-ov-handle').nth(2);
    const at = await handle.boundingBox();
    if (!at) throw new Error('no handle');
    await page.mouse.move(at.x + at.width / 2, at.y + at.height / 2);
    await page.mouse.down();
    await page.mouse.move(at.x + at.width / 2 + 40, at.y + at.height / 2 + 30, { steps: 5 });
    await page.mouse.up();
    await expect.poll(async () => ((await corner(2)) ?? 0) > (beforeDrag ?? 0) + 20).toBe(true);

    // Undo puts the drag back, redo does it again.
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect.poll(() => corner(2)).toBe(beforeDrag);
    await page.getByRole('button', { name: 'Redo' }).click();
    await expect.poll(async () => ((await corner(2)) ?? 0) > (beforeDrag ?? 0) + 20).toBe(true);

    // Remove it from the Map; the entry stays, and the pin is still there.
    await page.getByRole('button', { name: 'Remove from this map' }).click();
    await expect(page.getByText('Old Town is no longer on this map.')).toBeVisible();
    expect((await w.read()).map((r) => r.name)).toEqual(['Harbour']);
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect
      .poll(async () => (await w.read()).map((r) => r.name).sort())
      .toEqual(['Harbour', 'Old Town']);
    expect(harbour.id).toBeTruthy();
  } finally {
    await page.context().close();
  }
});

test('the children of a place, the look, the legend and the settings', async ({ browser }) => {
  const w = await world();
  const realm = await w.place('Realm');
  for (const name of ['Alder', 'Birch', 'Cedar']) await w.place(name, realm.id);
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
      params: { path: { ...w.path, map_id: w.chart.id, entry_id: realm.id } },
      body: {
        geometry: {
          format: 'lorenzo.geometry/1',
          parts: [
            {
              shape: 'polygon',
              rings: [
                [
                  [100, 100],
                  [600, 100],
                  [600, 500],
                  [100, 500],
                ],
              ],
            },
          ],
        },
        role: 'territory',
        z: 0,
      },
    }),
  );
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    // The legend names the roles on the Map.
    await page.getByText('Legend', { exact: true }).click();
    await expect(page.locator('.map-legend-item')).toContainText(['Territory']);
    // Place the children: three pins inside the territory, in one go.
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.locator('.map-places').getByRole('button', { name: /Realm/ }).click();
    await expect(page.getByText('3 of the places inside Realm are not on this map.')).toBeVisible();
    await page.getByRole('button', { name: 'Place 3 inside it' }).click();
    await expect(page.getByText('Placed 3 places inside Realm.')).toBeVisible();
    const rows = await w.read();
    expect(rows.map((r) => r.name).sort()).toEqual(['Alder', 'Birch', 'Cedar', 'Realm']);
    for (const row of rows.filter((r) => r.name !== 'Realm')) {
      const at = geometryOf(row).parts[0]?.at ?? [0, 0];
      expect(at[0]).toBeGreaterThan(100);
      expect(at[0]).toBeLessThan(600);
      expect(at[1]).toBeGreaterThan(100);
      expect(at[1]).toBeLessThan(500);
    }
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect(page.getByText('Undone.')).toBeVisible();
    expect(await w.read()).toHaveLength(1);

    // The look: the viewer's choice, remembered.
    await page.getByLabel('Look').selectOption('plain');
    await expect(page.locator('.map-stage svg')).toHaveAttribute('data-theme', 'plain');
    await page.reload();
    await expect(page.locator('.map-stage svg')).toHaveAttribute('data-theme', 'plain');
    await page.getByLabel('Look').selectOption('map');
    await expect(page.locator('.map-stage svg')).toHaveAttribute('data-theme', 'default');

    // The Map's own theme name, by the settings.
    await page.getByLabel('How it is drawn unless a viewer chooses').selectOption('plain');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await expect(page.locator('.map-stage svg')).toHaveAttribute('data-theme', 'plain');
    const header = await ok(
      w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
        params: { path: { ...w.path, map_id: w.chart.id } },
      }),
    );
    expect(header.theme_hint).toBe('plain');
    // The sheet: a new width.
    await page.getByLabel('Width', { exact: true }).fill('2000');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByLabel('Width', { exact: true })).toHaveValue('2000');
  } finally {
    await page.context().close();
  }
});

test('a refused drawing keeps the draft, and a player has no tools', async ({ browser }) => {
  const w = await world();
  await w.place('Marsh');
  const page = await signedIn(browser, w.subject);
  const player = await signedIn(browser, w.playerSubject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.getByRole('button', { name: 'Area', exact: true }).click();
    await page.getByLabel('Find an entry by name').fill('Marsh');
    await page
      .locator('.map-edit-panel')
      .getByRole('button', { name: /^Marsh/ })
      .click();
    // A bow tie crosses itself: the API refuses it and nothing is written.
    for (const [x, y] of [
      [0.3, 0.3],
      [0.6, 0.6],
      [0.6, 0.3],
      [0.3, 0.6],
    ] as const) {
      await clickSheet(page, x, y);
    }
    await page.keyboard.press('Enter');
    await expect(page.getByRole('alert').first()).toBeVisible();
    expect(await w.read()).toHaveLength(0);
    // A key takes a point back, and Escape starts over.
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('Backspace');
    await page.keyboard.press('Escape');

    // A player sees the Map and the legend, and none of the controls.
    await player.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(player.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await expect(player.getByRole('button', { name: 'Edit this map' })).toHaveCount(0);
    await expect(player.getByRole('heading', { name: 'Settings' })).toHaveCount(0);
    await expect(player.getByLabel('Look')).toBeVisible();
    await player.goto(`/maps/?tenant=${w.tenant.id}`);
    await expect(player.getByRole('link', { name: 'Sword Coast', exact: true })).toBeVisible();
    await expect(player.getByRole('button', { name: 'Make the Map' })).toHaveCount(0);
  } finally {
    await page.context().close();
    await player.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`editing a Map has no accessibility errors in ${theme}`, async ({ browser }) => {
    const w = await world();
    const place = await w.place('Keep');
    await ok(
      w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
        params: { path: { ...w.path, map_id: w.chart.id, entry_id: place.id } },
        body: {
          geometry: {
            format: 'lorenzo.geometry/1',
            parts: [{ shape: 'point', at: [300, 300] }],
          },
          role: 'site',
          z: 0,
        },
      }),
    );
    const page = await signedIn(browser, w.subject, theme);
    try {
      await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
      await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Edit this map' }).click();
      await page.getByText('Legend', { exact: true }).click();
      await page.locator('.map-places').getByRole('button', { name: /Keep/ }).click();
      await expect(page.getByRole('heading', { name: 'Change Keep' })).toBeVisible();
      const result = await new AxeBuilder({ page }).analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.getByRole('button', { name: 'Circle', exact: true }).click();
      const drawing = await new AxeBuilder({ page }).analyze();
      expect(drawing.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}
