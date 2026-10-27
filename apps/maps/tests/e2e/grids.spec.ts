import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { cellAt, cellCentre, type GridSpec } from '@lorenzo/map-renderer';
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

const F = 'lorenzo.map-system/1';
const EXTENT = [0, 0, 1000, 800];
const SQUARE = { format: F, kind: 'square', extent: EXTENT, cell: { size: 100 } };
const HEX = {
  format: F,
  kind: 'hex',
  orientation: 'pointy',
  extent: EXTENT,
  cell: { size: 100 },
  measure: { per_cell: 6, unit: 'miles' },
  sub: { aperture: 3 },
};
const PLANE = { format: F, kind: 'plane', extent: EXTENT };

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
  const makeMap = (name: string, system: Record<string, unknown>, view?: Record<string, unknown>) =>
    ok(
      gm.POST('/tenants/{tenant_id}/maps', {
        params: { path },
        body: { name, system, is_public: true, ...(view ? { view } : {}) },
      }),
    );
  const place = (name: string) =>
    ok(
      gm.POST('/tenants/{tenant_id}/locations', {
        params: { path },
        body: { name, is_public: true },
      }),
    );
  const read = async (map: string) =>
    (
      await ok(
        gm.GET('/tenants/{tenant_id}/maps/{map_id}/placements', {
          params: { path: { ...path, map_id: map } },
        }),
      )
    ).items;
  return { subject, gm, tenant, player, playerSubject, path, makeMap, place, read };
}

type Geometry = { parts: { shape: string; at?: number[]; rings?: number[][][] }[] };
const geometryOf = (row: { geometry: unknown } | undefined): Geometry =>
  (row?.geometry ?? { parts: [] }) as Geometry;

/** A click at a fraction of the drawing. */
async function clickSheet(page: Page, fx: number, fy: number) {
  const box = await page.locator('.map-stage').boundingBox();
  if (!box) throw new Error('the map has no box');
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
}

const gridPaths = (page: Page) => page.locator('.map-stage path.m-grid');

test('a writer makes a square, a rectangular and a hex Map, the hex one only with its orientation', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/maps/?tenant=${w.tenant.id}`);
    // A square grid.
    await page.getByLabel('Name', { exact: true }).fill('Chessboard');
    await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('square');
    await page.getByLabel('Cell size').filter({ visible: true }).fill('100');
    await expect(page.getByText(/About 80 cells/)).toBeVisible();
    await page.getByRole('button', { name: 'Make the Map' }).click();
    await expect(page.getByRole('heading', { name: 'Chessboard', exact: true })).toBeVisible();
    await expect(gridPaths(page)).toHaveCount(1);

    // A hex grid is not made until the hexes are said to be flat or pointed.
    await page.goto(`/maps/?tenant=${w.tenant.id}`);
    await page.getByLabel('Name', { exact: true }).fill('Hexcrawl');
    await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('hex');
    await page.getByLabel('Cell size').filter({ visible: true }).fill('100');
    await page.getByRole('button', { name: 'Make the Map' }).click();
    await expect(
      page.getByText('Say whether the hexes are flat-topped or pointed-top.'),
    ).toBeVisible();
    await page.getByRole('combobox', { name: 'Hexes are' }).selectOption('flat');
    await page.getByLabel('One cell is').fill('6');
    await page.getByLabel('of (a unit)').fill('miles');
    await page.getByRole('button', { name: 'Make the Map' }).click();
    await expect(page.getByRole('heading', { name: 'Hexcrawl', exact: true })).toBeVisible();
    await expect(gridPaths(page)).toHaveCount(1);

    // A rectangular grid.
    await page.goto(`/maps/?tenant=${w.tenant.id}`);
    await page.getByLabel('Name', { exact: true }).fill('Brickwork');
    await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('rect');
    await page.getByLabel('Cell width').filter({ visible: true }).fill('120');
    await page.getByLabel('Cell height').filter({ visible: true }).fill('80');
    await page.getByRole('button', { name: 'Make the Map' }).click();
    await expect(page.getByRole('heading', { name: 'Brickwork', exact: true })).toBeVisible();

    const made = await ok(w.gm.GET('/tenants/{tenant_id}/maps', { params: { path: w.path } }));
    const kinds = Object.fromEntries(
      await Promise.all(
        made.items.map(async (m) => {
          const header = await ok(
            w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
              params: { path: { ...w.path, map_id: m.id } },
            }),
          );
          return [m.name, header.system] as const;
        }),
      ),
    );
    expect(kinds.Chessboard).toMatchObject({ kind: 'square', cell: { size: 100 } });
    expect(kinds.Hexcrawl).toMatchObject({
      kind: 'hex',
      orientation: 'flat',
      measure: { per_cell: 6, unit: 'miles' },
    });
    expect(kinds.Brickwork).toMatchObject({ kind: 'rect', cell: { width: 120, height: 80 } });
  } finally {
    await page.context().close();
  }
});

test('on a grid the pointer says its cell, a pin snaps to a cell and the Cells tool draws regions', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Hexes', HEX);
  const keep = await w.place('Keep');
  const marsh = await w.place('Marsh');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Hexes', exact: true })).toBeVisible();
    await expect(gridPaths(page)).toHaveCount(1);
    await expect(page.locator('.map-stage path.m-grid-sub')).toHaveCount(1);
    // The cell under the pointer, in words.
    const box = await page.locator('.map-stage').boundingBox();
    if (!box) throw new Error('no box');
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await expect(page.locator('.map-cell')).toContainText(/Column \d+, row \d+/);

    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.getByRole('button', { name: 'Pin', exact: true }).click();
    await page.getByLabel('Find an entry by name').fill('Keep');
    await page
      .locator('.map-edit-panel')
      .getByRole('button', { name: /^Keep location$/ })
      .click();
    await clickSheet(page, 0.4, 0.4);
    await expect.poll(async () => (await w.read(chart.id)).length).toBe(1);
    const pinned = geometryOf((await w.read(chart.id))[0]).parts[0]?.at as [number, number];
    const grid = HEX as unknown as GridSpec;
    const centre = cellCentre(grid, [0, 0, 1000, 800], cellAt(grid, [0, 0, 1000, 800], pinned));

    expect(Math.abs(pinned[0] - centre[0])).toBeLessThan(0.011);
    expect(Math.abs(pinned[1] - centre[1])).toBeLessThan(0.011);
    // A selected pin says its cell.
    await expect(page.getByText(/In cell: Column \d+, row \d+/)).toBeVisible();

    // The Cells tool: a region of three hexes.
    await page.getByRole('button', { name: 'Cells', exact: true }).click();
    await page.getByLabel('Find an entry by name').fill('Marsh');
    await page
      .locator('.map-edit-panel')
      .getByRole('button', { name: /^Marsh location$/ })
      .click();
    for (const [x, y] of [
      [0.2, 0.3],
      [0.3, 0.3],
      [0.25, 0.4],
    ] as const) {
      await clickSheet(page, x, y);
    }
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Change Marsh' })).toBeVisible();
    const parts = geometryOf((await w.read(chart.id)).find((r) => r.name === 'Marsh')).parts;

    expect(parts).toHaveLength(3);
    expect(parts.every((p) => p.shape === 'polygon' && p.rings?.[0]?.length === 6)).toBe(true);
    // The cells are listed, one can be added by number, and one taken away.
    await expect(page.locator('.map-edit-panel').getByText(/^Column \d+, row \d+$/)).toHaveCount(3);
    await page.getByLabel('Column', { exact: true }).fill('10');
    await page.getByLabel('Row', { exact: true }).fill('7');
    await page.getByRole('button', { name: 'Add cell' }).click();
    await expect
      .poll(
        async () =>
          geometryOf((await w.read(chart.id)).find((r) => r.name === 'Marsh')).parts.length,
      )
      .toBe(4);
    await page.getByRole('button', { name: 'Remove Column 10, row 7' }).click();
    await expect
      .poll(
        async () =>
          geometryOf((await w.read(chart.id)).find((r) => r.name === 'Marsh')).parts.length,
      )
      .toBe(3);
    expect(keep.id && marsh.id).toBeTruthy();
  } finally {
    await page.context().close();
  }
});

test('a plane draws a grid over itself, a hex Map under places refuses to turn its hexes, and a fine grid says so', async ({
  browser,
}) => {
  const w = await world();
  const plane = await w.makeMap('Plain sheet', PLANE);
  const hexes = await w.makeMap('Hex sheet', HEX);
  const fine = await w.makeMap('Fine sheet', { ...SQUARE, cell: { size: 4 } });
  const one = await w.place('One');
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
      params: { path: { ...w.path, map_id: hexes.id, entry_id: one.id } },
      body: {
        geometry: { format: 'lorenzo.geometry/1', parts: [{ shape: 'point', at: [100, 100] }] },
        role: 'site',
        z: 0,
      },
    }),
  );
  const page = await signedIn(browser, w.subject);
  try {
    // A visual grid over a plane.
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${plane.id}`);
    await expect(page.getByRole('heading', { name: 'Plain sheet', exact: true })).toBeVisible();
    await expect(gridPaths(page)).toHaveCount(0);
    await page.getByLabel('Draw a grid over it').check();
    await page.getByRole('combobox', { name: 'The grid is' }).selectOption('square');
    await page.getByLabel('Cell size').filter({ visible: true }).fill('80');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByRole('heading', { name: 'Plain sheet', exact: true })).toBeVisible();
    await expect(gridPaths(page)).toHaveCount(1);
    const header = await ok(
      w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
        params: { path: { ...w.path, map_id: plane.id } },
      }),
    );
    expect(header.view).toEqual({ grid: { kind: 'square', cell: { size: 80 } } });
    // The Grid switch hides it.
    await page.getByLabel('Grid', { exact: true }).uncheck();
    await expect(gridPaths(page)).toHaveCount(0);

    // Turning the hexes under a place is refused, and the form keeps what was typed.
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${hexes.id}`);
    await expect(page.getByRole('heading', { name: 'Hex sheet', exact: true })).toBeVisible();
    await page.getByRole('combobox', { name: 'Hexes are' }).selectOption('flat');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByText(/cannot turn its hexes/)).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Hexes are' })).toHaveValue('flat');
    // A cell of another size is allowed, and said to line up less.
    await page.getByRole('combobox', { name: 'Hexes are' }).selectOption('pointy');
    await page.getByLabel('Cell size').filter({ visible: true }).fill('90');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect
      .poll(
        async () =>
          (
            await ok(
              w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
                params: { path: { ...w.path, map_id: hexes.id } },
              }),
            )
          ).system,
      )
      .toMatchObject({ orientation: 'pointy', cell: { size: 90 } });

    // A grid too fine to draw says so.
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${fine.id}`);
    await expect(page.getByRole('heading', { name: 'Fine sheet', exact: true })).toBeVisible();
    await expect(page.getByText('Zoom in to see the grid.')).toBeVisible();
    await expect(gridPaths(page)).toHaveCount(0);
  } finally {
    await page.context().close();
  }
});

test('a player sees the grid and the cell words and none of the tools', async ({ browser }) => {
  const w = await world();
  const chart = await w.makeMap('Squares', SQUARE);
  const page = await signedIn(browser, w.playerSubject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Squares', exact: true })).toBeVisible();
    await expect(gridPaths(page)).toHaveCount(1);
    await expect(page.getByLabel('Grid', { exact: true })).toBeChecked();
    const box = await page.locator('.map-stage').boundingBox();
    if (!box) throw new Error('no box');
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await expect(page.locator('.map-cell')).toContainText(/Column \d+, row \d+/);
    await expect(page.getByRole('button', { name: 'Edit this map' })).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Settings' })).toHaveCount(0);
  } finally {
    await page.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`a grid Map in the Cells tool has no accessibility errors in ${theme}`, async ({
    browser,
  }) => {
    const w = await world();
    const chart = await w.makeMap('Hexes', HEX);
    await w.place('Keep');
    const page = await signedIn(browser, w.subject, theme);
    try {
      await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
      await expect(page.getByRole('heading', { name: 'Hexes', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Edit this map' }).click();
      await page.getByRole('button', { name: 'Cells', exact: true }).click();
      await page.getByLabel('Find an entry by name').fill('Keep');
      await page
        .locator('.map-edit-panel')
        .getByRole('button', { name: /^Keep location$/ })
        .click();
      await clickSheet(page, 0.3, 0.3);
      const result = await new AxeBuilder({ page }).analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.goto(`/maps/?tenant=${w.tenant.id}`);
      await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('hex');
      const form = await new AxeBuilder({ page }).analyze();
      expect(form.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}
