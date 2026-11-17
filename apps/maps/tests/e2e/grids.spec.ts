import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { cellAt, cellCentre, type GridSpec } from '@lorenzo/map-renderer';
import { type Browser, expect, type Page, test } from '@playwright/test';
import { cellFill } from '../../src/lib/cell-fill.ts';
import { cellsGeometry, cellsOf } from '../../src/lib/cells-edit.ts';
import { regionOf } from '../../src/lib/generator.ts';
import { apiAs, ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';
import { openControl, openPanel, stageBox } from './support/map-ui.ts';

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
/** How many cells a drawing holds, read as the editor reads them (ADR 0481); 0 when it is no cells. */
const cellsIn = (row: { geometry: unknown } | undefined, grid: unknown): number =>
  cellsOf(
    (row?.geometry ?? { parts: [] }) as never,
    grid as GridSpec,
    EXTENT as unknown as [number, number, number, number],
  )?.length ?? 0;

const geometryOf = (row: { geometry: unknown } | undefined): Geometry =>
  (row?.geometry ?? { parts: [] }) as Geometry;

/** A click at a fraction of the drawing. */
async function clickSheet(page: Page, fx: number, fy: number) {
  const box = await stageBox(page);
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
    await page.getByRole('button', { name: 'Make a Map', exact: true }).click();
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
    await page.getByRole('button', { name: 'Make a Map', exact: true }).click();
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
    await page.getByRole('button', { name: 'Make a Map', exact: true }).click();
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
    const box = await stageBox(page);
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
    await expect(page.locator('.map-panel')).toContainText(/In cell: Column \d+, row \d+/);

    // The Cells tool: a region of three hexes.
    await page.getByRole('button', { name: 'Cells', exact: true }).click();
    await page.getByLabel('Find an entry by name').fill('Marsh');
    await page
      .locator('.map-edit-panel')
      .getByRole('button', { name: /^Marsh location$/ })
      .click();
    for (const [x, y] of [
      [0.45, 0.3],
      [0.55, 0.3],
      [0.5, 0.4],
    ] as const) {
      await clickSheet(page, x, y);
    }
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Change Marsh' })).toBeVisible();
    const marshRow = (await w.read(chart.id)).find((r) => r.name === 'Marsh');
    const parts = geometryOf(marshRow).parts;

    // Three cells, written as outlines (ADR 0481): as many parts as patches, never more than cells.
    expect(cellsIn(marshRow, HEX)).toBe(3);
    expect(parts.length).toBeLessThanOrEqual(3);
    expect(parts.every((p) => p.shape === 'polygon')).toBe(true);
    // The cells are listed, one can be added by number, and one taken away.
    await expect(page.locator('.map-edit-panel').getByText(/^Column \d+, row \d+$/)).toHaveCount(3);
    await page.getByLabel('Column', { exact: true }).fill('10');
    await page.getByLabel('Row', { exact: true }).fill('7');
    await page.getByRole('button', { name: 'Add cell' }).click();
    await expect
      .poll(async () =>
        cellsIn(
          (await w.read(chart.id)).find((r) => r.name === 'Marsh'),
          HEX,
        ),
      )
      .toBe(4);
    await page.getByRole('button', { name: 'Remove Column 10, row 7' }).click();
    await expect
      .poll(async () =>
        cellsIn(
          (await w.read(chart.id)).find((r) => r.name === 'Marsh'),
          HEX,
        ),
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
    await openPanel(page, 'Settings');
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
    await openControl(page, 'Layers');
    await page.getByRole('checkbox', { name: 'Grid', exact: true }).uncheck();
    await expect(gridPaths(page)).toHaveCount(0);

    // Turning the hexes under a place is refused, and the form keeps what was typed.
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${hexes.id}`);
    await expect(page.getByRole('heading', { name: 'Hex sheet', exact: true })).toBeVisible();
    await openPanel(page, 'Settings');
    await page.getByRole('combobox', { name: 'Hexes are' }).selectOption('flat');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await openPanel(page, 'Settings');
    await expect(page.getByText(/cannot turn its hexes/)).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Hexes are' })).toHaveValue('flat');
    // A cell of another size is allowed, and said to line up less.
    await openPanel(page, 'Settings');
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

test('snapping is an option of the tool: off in the Options tab, on again from the command line', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Hexes', HEX);
  await w.place('Keep');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Hexes', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.getByRole('button', { name: 'Pin', exact: true }).click();
    // The option is drawn with the tool, in the panel, and is on at first.
    const snap = page.getByRole('group', { name: 'Options of Pin' }).getByLabel('Snap to the grid');
    await expect(snap).toBeChecked();
    await snap.uncheck();
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

    // Not snapped: the pin is where the click was, not at its cell's centre.
    expect(Math.hypot(pinned[0] - centre[0], pinned[1] - centre[1])).toBeGreaterThan(0.5);

    // The same option from the command line, for the tool that is on (Select shares it).
    const command = page.getByLabel('Command', { exact: true });
    const answer = page.locator('.map-command-answer');
    await command.fill('SNAP ON');
    await command.press('Enter');
    await expect(answer).toHaveText('Snap to the grid is on.');
    await expect(
      page.getByRole('group', { name: 'Options of Select' }).getByLabel('Snap to the grid'),
    ).toBeChecked();
    await command.fill('SNAP sideways');
    await command.press('Enter');
    await expect(answer).toHaveText('SNAP takes ON or OFF.');
  } finally {
    await page.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`a fill by wave function collapse learns from the cells drawn and fills a region, in ${theme}`, async ({
    browser,
  }) => {
    const w = await world();
    const chart = await w.makeMap('Tunnels', SQUARE);
    const grid = SQUARE as unknown as GridSpec;
    const extent = [0, 0, 1000, 800] as const;
    const block = (c0: number, r0: number, c1: number, r1: number) => {
      const cells: [number, number][] = [];
      for (let row = r0; row <= r1; row += 1) {
        for (let col = c0; col <= c1; col += 1) cells.push([col, row]);
      }
      return cells;
    };
    const draw = async (name: string, parts: unknown[]) => {
      const entry = await w.place(name);
      await ok(
        w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
          params: { path: { ...w.path, map_id: chart.id, entry_id: entry.id } },
          body: { geometry: { format: 'lorenzo.geometry/1', parts }, z: 0 } as never,
        }),
      );
      return entry;
    };
    // The example: stripes, a row of Wall and a row of Floor, twice, four cells wide.
    const stripes = {
      Wall: [...block(0, 0, 3, 0), ...block(0, 2, 3, 2)],
      Floor: [...block(0, 1, 3, 1), ...block(0, 3, 3, 3)],
    };
    const wall = await draw('Wall', cellsGeometry(grid, extent, stripes.Wall).parts as unknown[]);
    const floor = await draw(
      'Floor',
      cellsGeometry(grid, extent, stripes.Floor).parts as unknown[],
    );
    // The region: an area over the cells of columns 5 to 8 and rows 4 to 7.
    await draw('Yard', [
      {
        shape: 'polygon',
        rings: [
          [
            [500, 400],
            [900, 400],
            [900, 800],
            [500, 800],
          ],
        ],
      },
    ]);
    const yard = regionOf(
      {
        name: 'Yard',
        geometry: {
          format: 'lorenzo.geometry/1',
          parts: [
            {
              shape: 'polygon',
              rings: [
                [
                  [500, 400],
                  [900, 400],
                  [900, 800],
                  [500, 800],
                ],
              ],
            },
          ],
        },
      },
      extent,
    );
    // What the fill makes of it for this seed, the entries in the order they are drawn.
    const tiles = [
      { id: wall.id, name: 'Wall', cells: stripes.Wall },
      { id: floor.id, name: 'Floor', cells: stripes.Floor },
    ].sort((a, b) => (a.id < b.id ? -1 : 1));
    const expected = cellFill(
      grid,
      extent,
      tiles,
      new Map(tiles.map((tile) => [tile.id, tile.cells])),
      yard,
      4821,
    );
    if (!expected.ok) throw new Error(expected.why);
    const gained = (name: string) => expected.tiles.find((t) => t.name === name)?.gained ?? [];
    // Stripes can only be stripes: the sixteen cells are eight of each.
    expect(gained('Wall')).toHaveLength(8);
    expect(gained('Floor')).toHaveLength(8);
    const cellsOn = async (name: string) =>
      cellsIn(
        (await w.read(chart.id)).find((r) => r.name === name),
        grid,
      );

    const page = await signedIn(browser, w.subject, theme);
    try {
      await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
      await expect(page.getByRole('heading', { name: 'Tunnels', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Edit this map' }).click();
      await openPanel(page, 'Places');
      await page.locator('.map-places').getByRole('button', { name: /Yard/ }).click();
      await expect(page.getByRole('heading', { name: 'Change Yard' })).toBeVisible();
      await page
        .getByRole('group', { name: 'Generate', exact: true })
        .getByRole('button', { name: 'Fill by wave function collapse', exact: true })
        .click();
      // No entry to choose: the tiles are the entries of the example.
      await expect(page.getByLabel('Find an entry by name')).toHaveCount(0);
      const command = page.getByLabel('Command', { exact: true });
      await command.fill('SEED 4821');
      await command.press('Enter');
      const preview = page.getByRole('group', { name: 'Preview' });
      await expect(preview.locator('.map-generator-result')).toHaveText(
        '16 cells of 2 tiles in Yard.',
      );
      // Each tile by name with what it would get, and one shape a tile on the Map.
      await expect(preview.locator('.map-generator-tiles li')).toHaveText(
        expected.tiles.map((tile) => `${tile.name}: 8 cells`),
      );
      await expect(page.locator('.map-stage .m-ov-area')).toHaveCount(2);
      expect(await cellsOn('Wall')).toBe(8);
      const result = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);

      // Apply: one batch, each entry keeps its example and gains its cells of the region.
      await preview.getByRole('button', { name: 'Apply' }).click();
      await expect.poll(() => cellsOn('Wall')).toBe(16);
      expect(await cellsOn('Floor')).toBe(16);
      const rows = await w.read(chart.id);
      for (const name of ['Wall', 'Floor'] as const) {
        const row = rows.find((r) => r.name === name);
        expect(row?.geometry).toEqual(
          cellsGeometry(grid, extent, [...stripes[name], ...gained(name)]),
        );
      }
      // The area it worked in is as it was, and the preview is gone.
      expect(geometryOf(rows.find((r) => r.name === 'Yard')).parts).toHaveLength(1);
      await expect(page.locator('.map-stage .m-ov-area')).toHaveCount(0);
      await openPanel(page, 'History');
      await expect(page.locator('.map-slideover')).toContainText(
        'Filled by wave function collapse, seed 4821: 16 cells of 2 tiles in Yard',
      );
      // Undo puts every entry back in one step.
      await page.getByRole('button', { name: 'Undo' }).click();
      await expect.poll(() => cellsOn('Wall')).toBe(8);
      expect(await cellsOn('Floor')).toBe(8);
    } finally {
      await page.context().close();
    }
  });
}

/** Two Maps of squares: one with stripes drawn as cells, and one to fill, with an area Yard. */
async function examplePair(w: Awaited<ReturnType<typeof world>>) {
  const grid = SQUARE as unknown as GridSpec;
  const extent = [0, 0, 1000, 800] as const;
  const caves = await w.makeMap('Old caves', SQUARE);
  const level = await w.makeMap('New level', SQUARE);
  const row = (r: number): [number, number][] => [0, 1, 2, 3].map((c): [number, number] => [c, r]);
  const stripes = { Wall: [...row(0), ...row(2)], Floor: [...row(1), ...row(3)] };
  const put = async (map: string, entry: string, geometry: unknown, z: number) =>
    ok(
      w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
        params: { path: { ...w.path, map_id: map, entry_id: entry } },
        body: { geometry, z } as never,
      }),
    );
  const wall = await w.place('Wall');
  const floor = await w.place('Floor');
  await put(caves.id, wall.id, cellsGeometry(grid, extent, stripes.Wall), 2);
  await put(caves.id, floor.id, cellsGeometry(grid, extent, stripes.Floor), 3);
  const ring = [
    [500, 400],
    [900, 400],
    [900, 800],
    [500, 800],
  ] as [number, number][];
  const yard = await w.place('Yard');
  await put(
    level.id,
    yard.id,
    { format: 'lorenzo.geometry/1', parts: [{ shape: 'polygon', rings: [ring] }] },
    0,
  );
  const region = regionOf(
    {
      name: 'Yard',
      geometry: { format: 'lorenzo.geometry/1', parts: [{ shape: 'polygon', rings: [ring] }] },
    },
    extent,
  );
  return { grid, extent, caves, level, stripes, wall, floor, region, put };
}

async function fillFrom(page: Page, w: Awaited<ReturnType<typeof world>>, level: { id: string }) {
  await page.goto(`/map/?tenant=${w.tenant.id}&id=${level.id}`);
  await expect(page.getByRole('heading', { name: 'New level', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Edit this map' }).click();
  await openPanel(page, 'Places');
  await page.locator('.map-places').getByRole('button', { name: /Yard/ }).click();
  await expect(page.getByRole('heading', { name: 'Change Yard' })).toBeVisible();
  await page
    .getByRole('group', { name: 'Generate', exact: true })
    .getByRole('button', { name: 'Fill by wave function collapse', exact: true })
    .click();
}

for (const theme of ['light', 'dark'] as const) {
  test(`a fill by wave function collapse learns from another Map and places its entries here, in ${theme}`, async ({
    browser,
  }) => {
    const w = await world();
    const pair = await examplePair(w);
    // Neither entry is on this Map yet: the fill places both, as they are drawn on the example.
    const tiles = [
      { id: pair.wall.id, name: 'Wall', cells: pair.stripes.Wall },
      { id: pair.floor.id, name: 'Floor', cells: pair.stripes.Floor },
    ];
    const expected = cellFill(pair.grid, pair.extent, tiles, new Map(), pair.region, 4821);
    if (!expected.ok) throw new Error(expected.why);
    const gained = (name: string) => expected.tiles.find((t) => t.name === name)?.gained ?? [];
    expect(gained('Wall')).toHaveLength(8);

    const page = await signedIn(browser, w.subject, theme);
    try {
      await fillFrom(page, w, pair.level);
      const command = page.getByLabel('Command', { exact: true });
      await command.fill('SEED 4821');
      await command.press('Enter');
      await command.fill('EXAMPLE old caves');
      await command.press('Enter');
      await expect(page.locator('.map-command-answer')).toContainText('Example is Old caves.');
      const preview = page.getByRole('group', { name: 'Preview' });
      await expect(preview).toContainText('It learns from the cells already drawn on Old caves');
      await expect(preview.locator('.map-generator-result')).toHaveText(
        '16 cells of 2 tiles in Yard.',
      );
      await expect(preview.locator('.map-generator-tiles li')).toHaveText([
        'Wall: 8 cells',
        'Floor: 8 cells',
      ]);
      await expect(page.getByRole('combobox', { name: 'Example', exact: true })).toHaveValue(
        pair.caves.id,
      );
      const result = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);

      // Apply: both entries are placed here, with the drawing order they have on the example.
      await preview.getByRole('button', { name: 'Apply' }).click();
      await expect.poll(async () => (await w.read(pair.level.id)).length).toBe(3);
      const rows = await w.read(pair.level.id);
      for (const [name, z] of [
        ['Wall', 2],
        ['Floor', 3],
      ] as const) {
        const row = rows.find((r) => r.name === name);
        expect(row?.geometry).toEqual(cellsGeometry(pair.grid, pair.extent, gained(name)));
        expect(row?.z).toBe(z);
      }
      // The example is as it was.
      expect(
        cellsIn(
          (await w.read(pair.caves.id)).find((r) => r.name === 'Wall'),
          pair.grid,
        ),
      ).toBe(8);
      await openPanel(page, 'History');
      await expect(page.locator('.map-slideover')).toContainText(
        'Filled by wave function collapse, seed 4821: 16 cells of 2 tiles in Yard',
      );
      // Undo takes both off this Map again.
      await page.getByRole('button', { name: 'Undo' }).click();
      await expect.poll(async () => (await w.read(pair.level.id)).length).toBe(1);
    } finally {
      await page.context().close();
    }
  });
}

test('a fill by wave function collapse from another Map refuses an entry drawn here otherwise, and offers Maps of its kind only', async ({
  browser,
}) => {
  const w = await world();
  const pair = await examplePair(w);
  await w.makeMap('Honeycomb', HEX);
  // Floor is a pin on this Map: the fill would have to take that drawing away.
  await pair.put(
    pair.level.id,
    pair.floor.id,
    { format: 'lorenzo.geometry/1', parts: [{ shape: 'point', at: [150, 150] }] },
    0,
  );
  const page = await signedIn(browser, w.subject);
  try {
    await fillFrom(page, w, pair.level);
    const example = page.getByRole('combobox', { name: 'Example', exact: true });
    // The hexes are not offered: only Maps with a grid of the kind this Map has.
    await expect(example.locator('option')).toHaveText(['This Map', 'Old caves']);
    await example.selectOption({ label: 'Old caves' });
    const preview = page.getByRole('group', { name: 'Preview' });
    await expect(preview.locator('.map-generator-result')).toHaveText(
      'Floor is drawn on this Map as something else than cells, and a Map holds one drawing for an entry. Take it off this Map first, or choose another example.',
    );
    await expect(preview.getByRole('button', { name: 'Apply' })).toBeDisabled();
    const command = page.getByLabel('Command', { exact: true });
    await command.fill('EXAMPLE Honeycomb');
    await command.press('Enter');
    await expect(page.locator('.map-command-answer')).toContainText(
      'No Map of the library with a grid of this kind is called Honeycomb.',
    );
    // Back to this Map, which has no cells drawn.
    await command.fill('EXAMPLE this');
    await command.press('Enter');
    await expect(page.locator('.map-command-answer')).toContainText('Example is this Map.');
    await expect(preview.locator('.map-generator-result')).toHaveText(
      'There is no example yet: draw some cells with the Cells tool first, and the fill learns from them.',
    );
    expect(await w.read(pair.level.id)).toHaveLength(2);
  } finally {
    await page.context().close();
  }
});

test('a fill gives an entry far more than 256 cells, written as outlines, and undo takes it back (ADR 0481)', async ({
  browser,
}) => {
  const w = await world();
  // A hall of small squares: 40 by 32, 1,280 cells.
  const FINE = { format: F, kind: 'square', extent: EXTENT, cell: { size: 25 } };
  const grid = FINE as unknown as GridSpec;
  const extent = [0, 0, 1000, 800] as const;
  const hall = await w.makeMap('Great hall', FINE);
  const row = (r: number): [number, number][] => [0, 1, 2, 3].map((c): [number, number] => [c, r]);
  const stripes = { Wall: [...row(0), ...row(2)], Floor: [...row(1), ...row(3)] };
  const put = async (name: string, cells: [number, number][]) => {
    const entry = await w.place(name);
    await ok(
      w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
        params: { path: { ...w.path, map_id: hall.id, entry_id: entry.id } },
        body: { geometry: cellsGeometry(grid, extent, cells), z: 0 } as never,
      }),
    );
    return entry;
  };
  const wall = await put('Wall', stripes.Wall);
  const floor = await put('Floor', stripes.Floor);
  const tiles = [
    { id: wall.id, name: 'Wall', cells: stripes.Wall },
    { id: floor.id, name: 'Floor', cells: stripes.Floor },
  ].sort((a, b) => (a.id < b.id ? -1 : 1));
  const expected = cellFill(
    grid,
    extent,
    tiles,
    new Map(tiles.map((tile) => [tile.id, tile.cells])),
    regionOf(null, extent),
    4821,
  );
  if (!expected.ok) throw new Error(expected.why);
  const wallCells = expected.tiles.find((t) => t.name === 'Wall')?.cells ?? [];
  // Far more than the 256 parts a drawing held before, as a few outlines.
  expect(wallCells.length).toBeGreaterThan(256);
  const cellsOn = async (name: string) =>
    cellsIn(
      (await w.read(hall.id)).find((r) => r.name === name),
      grid,
    );

  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${hall.id}`);
    await expect(page.getByRole('heading', { name: 'Great hall', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('w');
    const command = page.getByLabel('Command', { exact: true });
    await command.fill('SEED 4821');
    await command.press('Enter');
    const preview = page.getByRole('group', { name: 'Preview' });
    await expect(preview.locator('.map-generator-result')).toHaveText(
      `${expected.count} in the whole sheet.`,
    );
    await preview.getByRole('button', { name: 'Apply' }).click();
    await expect.poll(() => cellsOn('Wall')).toBe(wallCells.length);
    const written = (await w.read(hall.id)).find((r) => r.name === 'Wall');
    expect(written?.geometry).toEqual(cellsGeometry(grid, extent, wallCells));
    expect(geometryOf(written).parts.length).toBeLessThan(wallCells.length);
    // Undo puts both entries back as they were, in one step.
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect.poll(() => cellsOn('Wall')).toBe(8);
    expect(await cellsOn('Floor')).toBe(8);
  } finally {
    await page.context().close();
  }
});

test('an area drawn along the grid lines is cells and keeps its points (ADR 0481)', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Rooms', SQUARE);
  const hall = await w.place('Hall');
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
      params: { path: { ...w.path, map_id: chart.id, entry_id: hall.id } },
      body: {
        geometry: {
          format: 'lorenzo.geometry/1',
          parts: [
            {
              shape: 'polygon',
              rings: [
                [
                  [200, 100],
                  [500, 100],
                  [500, 300],
                  [200, 300],
                ],
              ],
            },
          ],
        },
        z: 0,
      } as never,
    }),
  );
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Rooms', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await openPanel(page, 'Places');
    await page.locator('.map-places').getByRole('button', { name: /Hall/ }).click();
    const panel = page.locator('.map-edit-panel');
    // Its six cells are listed, and its four corners are points to change.
    await expect(panel.getByRole('heading', { name: 'Cells' })).toBeVisible();
    await expect(panel.getByText(/^Column \d+, row \d+$/)).toHaveCount(6);
    await expect(panel.getByRole('heading', { name: 'Points' })).toBeVisible();
    const result = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
    expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
  } finally {
    await page.context().close();
  }
});

test('a fill by wave function collapse says what is missing: no example, or a tile too large', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Empty', SQUARE);
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Empty', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('w');
    const preview = page.getByRole('group', { name: 'Preview' });
    await expect(preview.locator('.map-generator-result')).toHaveText(
      'There is no example yet: draw some cells with the Cells tool first, and the fill learns from them.',
    );
    await expect(preview.getByRole('button', { name: 'Apply' })).toBeDisabled();
    const command = page.getByLabel('Command', { exact: true });
    await command.fill('APPLY');
    await command.press('Enter');
    await expect(page.locator('.map-command-answer')).toContainText('There is no example yet');
    expect(await w.read(chart.id)).toHaveLength(0);
    await preview.getByRole('button', { name: 'Discard' }).click();

    // One entry drawn with the Cells tool is the whole example: every cell of the sheet would be
    // it, 80 of them, one outline, which a drawing holds (ADR 0481); so the fill is offered.
    await page.getByRole('button', { name: 'Cells', exact: true }).click();
    await page.getByLabel('Or make a new Location, named').fill('Rock');
    await page.getByRole('button', { name: 'Draw a new Location' }).click();
    await clickSheet(page, 0.25, 0.25);
    await clickSheet(page, 0.45, 0.25);
    await page.keyboard.press('Enter');
    await expect.poll(async () => (await w.read(chart.id)).length).toBe(1);
    expect(cellsIn((await w.read(chart.id))[0], SQUARE)).toBe(2);
    // The drawing just made is selected, and a selected area is where a fill works, never a tile
    // of it; Escape clears the selection, so the fill works on the whole sheet.
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('Escape');
    await page.keyboard.press('w');
    await expect(
      page.getByRole('group', { name: 'Preview' }).locator('.map-generator-result'),
    ).toHaveText('80 cells of 1 tile in the whole sheet.');
  } finally {
    await page.context().close();
  }
});

test('cells that would not land on cells of the grid are not moved, and the Map says why (ADR 0490)', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Hexes', HEX);
  const grid = HEX as unknown as GridSpec;
  const marsh = await w.place('Marsh');
  const drawn = cellsGeometry(
    grid,
    [0, 0, 1000, 800],
    [
      [1, 1],
      [2, 1],
      [2, 2],
    ],
  );
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
      params: { path: { ...w.path, map_id: chart.id, entry_id: marsh.id } },
      body: { geometry: drawn, z: 0 } as never,
    }),
  );
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Hexes', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await openPanel(page, 'Places');
    await page.locator('.map-places').getByRole('button', { name: /Marsh/ }).click();
    const command = page.getByLabel('Command', { exact: true });
    // Mirrored down, the offset rows of pointed-top hexes would not meet whole cells.
    await command.fill('MIRROR DOWN');
    await command.press('Enter');
    await expect(page.locator('.map-command-answer')).toHaveText(
      'Mirrored down, its cells would not land on whole cells of this grid. Nothing was changed.',
    );
    expect((await w.read(chart.id))[0]?.geometry).toEqual(drawn);
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
    await openControl(page, 'Layers');
    await expect(page.getByRole('checkbox', { name: 'Grid', exact: true })).toBeChecked();
    const box = await stageBox(page);
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
      const result = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.goto(`/maps/?tenant=${w.tenant.id}`);
      await page.getByRole('button', { name: 'Make a Map', exact: true }).click();
      await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('hex');
      const form = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(form.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}
