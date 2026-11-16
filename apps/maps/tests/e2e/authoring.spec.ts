import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { type Browser, expect, type Page, test } from '@playwright/test';
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
  const box = await stageBox(page);
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
    await page.getByRole('button', { name: 'Make a Map', exact: true }).click();
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
    await expect(page.locator('.map-places .map-place', { hasText: 'Harbour' })).toHaveCount(1);
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
    // The corner moves while the redo is still saving; the editor ignores a click that lands
    // mid-save, and "Remove from this map" is not disabled then. The status line is the redo's
    // last word, so wait for it.
    await expect(page.getByText('Done again.')).toBeVisible();

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
    await openControl(page, 'Legend');
    await expect(page.locator('.map-legend-item')).toContainText(['Territory']);
    // Place the children: three pins inside the territory, in one go.
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await openPanel(page, 'Places');
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
    await openControl(page, 'Look');
    await page.getByLabel('Look').selectOption('plain');
    await expect(page.locator('.map-stage svg')).toHaveAttribute('data-theme', 'plain');
    await page.reload();
    await expect(page.locator('.map-stage svg')).toHaveAttribute('data-theme', 'plain');
    await openControl(page, 'Look');
    await page.getByLabel('Look').selectOption('map');
    await expect(page.locator('.map-stage svg')).toHaveAttribute('data-theme', 'default');

    // The Map's own theme name, by the settings.
    await openPanel(page, 'Settings');
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
    await openPanel(page, 'Settings');
    await page.getByLabel('Width', { exact: true }).fill('2000');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await openPanel(page, 'Settings');
    await expect(page.getByLabel('Width', { exact: true })).toHaveValue('2000');
  } finally {
    await page.context().close();
  }
});

test('editing a point keeps the height a line carries', async ({ browser }) => {
  const w = await world();
  const ridge = await w.place('Ridge');
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
      params: { path: { ...w.path, map_id: w.chart.id, entry_id: ridge.id } },
      body: {
        geometry: {
          format: 'lorenzo.geometry/1',
          parts: [
            {
              shape: 'polyline',
              pts: [
                [200, 200],
                [500, 260],
                [700, 220],
              ],
              value: 250,
              unit: 'm',
            },
          ],
        },
        role: 'isoline',
        z: 0,
      },
    }),
  );
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await openPanel(page, 'Places');
    await page.locator('.map-places').getByRole('button', { name: /Ridge/ }).click();
    await expect(page.getByRole('heading', { name: 'Change Ridge' })).toBeVisible();
    const part = async () =>
      geometryOf((await w.read()).find((r) => r.name === 'Ridge')).parts[0] as
        | { pts?: number[][]; value?: number; unit?: string }
        | undefined;
    // A point by number, then a point taken away: the height stays with the line each time.
    await page.getByRole('group', { name: 'Point 1' }).getByLabel('x').fill('240');
    await page.getByRole('group', { name: 'Point 1' }).getByLabel('x').press('Tab');
    await expect.poll(async () => (await part())?.pts?.[0]?.[0]).toBe(240);
    expect(await part()).toMatchObject({ value: 250, unit: 'm' });
    await page.getByRole('button', { name: 'Remove point 2' }).click();
    await expect.poll(async () => (await part())?.pts?.length).toBe(2);
    expect(await part()).toMatchObject({ value: 250, unit: 'm' });
    // Undo writes back what it was, height and all.
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect.poll(async () => (await part())?.pts?.length).toBe(3);
    expect(await part()).toMatchObject({ value: 250, unit: 'm' });
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
    await openControl(player, 'Look');
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
      await openControl(page, 'Legend');
      await openPanel(page, 'Places');
      await page.locator('.map-places').getByRole('button', { name: /Keep/ }).click();
      await expect(page.getByRole('heading', { name: 'Change Keep' })).toBeVisible();
      const result = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.getByRole('button', { name: 'Circle', exact: true }).click();
      const drawing = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(drawing.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      // A tool with an option of its own: Spline and its Tension.
      await page.getByRole('button', { name: 'Spline', exact: true }).click();
      await expect(
        page.getByRole('group', { name: 'Options of Spline' }).getByLabel('Tension'),
      ).toBeVisible();
      const spline = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(spline.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.getByRole('button', { name: 'Freehand', exact: true }).click();
      await expect(
        page.getByRole('group', { name: 'Options of Freehand' }).getByLabel('Tolerance (pixels)'),
      ).toBeVisible();
      const freehand = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(freehand.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.getByRole('button', { name: 'Height line', exact: true }).click();
      await expect(
        page.getByRole('group', { name: 'Options of Height line' }).getByLabel('Unit'),
      ).toBeVisible();
      const heightLine = await new AxeBuilder({ page }).exclude('.shell-bottom').analyze();
      expect(heightLine.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}

test('the toolbox is drawn from the tool registry: groups, one key a tool, and planned tools that say so', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    // The tools are in their groups; Cells waits for a grid, and the planned ones are in All tools.
    const place = page.getByRole('group', { name: 'Place', exact: true });
    await expect(place.getByRole('button', { name: 'Pin', exact: true })).toBeVisible();
    await expect(place.getByRole('button', { name: 'Circle', exact: true })).toBeVisible();
    await expect(page.getByRole('group', { name: 'Draw', exact: true })).toContainText('Area');
    await expect(page.getByRole('button', { name: 'Cells', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Height brush', exact: true })).toHaveCount(0);
    // One key a tool, while the drawing has the focus; the page's own keys do not see them.
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('p');
    await expect(page.getByRole('button', { name: 'Pin', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await page.keyboard.press('l');
    await expect(page.getByRole('button', { name: 'Line', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    const address = page.url();
    await page.keyboard.press('g');
    await expect(page.getByText('Cells is not available on this Map.')).toBeVisible();
    expect(page.url()).toBe(address);
    await page.keyboard.press('h');
    await expect(page.getByText(/Height brush is planned\./)).toBeVisible();
    // All tools lists every tool, finds one by a few words and says which are planned.
    await page.getByRole('button', { name: 'All tools' }).click();
    await page.getByLabel('Find a tool').fill('cave');
    const cave = page.getByRole('button', { name: 'Cave system', exact: true });
    await expect(cave).toHaveAttribute('aria-disabled', 'true');
    await expect(page.locator('.map-all-tools-list')).toContainText('planned');
    await cave.click({ force: true });
    await expect(page.getByText(/Cave system is planned\./)).toBeVisible();
    // A key typed into a field is the field's.
    await page.getByLabel('Find a tool').fill('');
    await page.getByLabel('Find a tool').press('p');
    await expect(page.getByLabel('Find a tool')).toHaveValue('p');
  } finally {
    await page.context().close();
  }
});

test('the outliner places a place, by button or by dragging, and History steps back to any step', async ({
  browser,
}) => {
  const w = await world();
  await w.place('Harbour');
  await w.place('Lighthouse');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await openPanel(page, 'Places');
    await expect(page.getByRole('button', { name: 'Place Harbour on the Map' })).toBeVisible();

    // The Place button puts it where the view is centred.
    await page.getByRole('button', { name: 'Place Harbour on the Map' }).click();
    await expect.poll(async () => (await w.read()).map((r) => r.name)).toEqual(['Harbour']);
    await expect(page.getByRole('button', { name: 'Place Harbour on the Map' })).toHaveCount(0);

    // Dragging a row onto the sheet puts it at the drop.
    const dataTransfer = await page.evaluateHandle(() => new DataTransfer());
    await page
      .getByRole('button', { name: 'Place Lighthouse on the Map' })
      .locator('xpath=..')
      .dispatchEvent('dragstart', { dataTransfer });
    const box = await stageBox(page);
    if (!box) throw new Error('the map has no box');
    await page.locator('.map-stage').dispatchEvent('drop', {
      dataTransfer,
      clientX: box.x + box.width * 0.3,
      clientY: box.y + box.height * 0.3,
    });
    await expect
      .poll(async () => (await w.read()).map((r) => r.name).sort())
      .toEqual(['Harbour', 'Lighthouse']);

    // History names each step, and any of them can be gone back to.
    await openPanel(page, 'History');
    const history = page.locator('.map-history');
    await expect(history.getByRole('button', { name: 'Placed Harbour' })).toBeVisible();
    await expect(history.getByRole('button', { name: 'Placed Lighthouse' })).toBeVisible();
    await history.getByRole('button', { name: 'Before any change' }).click();
    await expect.poll(async () => (await w.read()).length).toBe(0);
    await expect(history.getByRole('button', { name: 'Placed Harbour' })).toHaveAttribute(
      'data-state',
      'undone',
    );
    await history.getByRole('button', { name: 'Placed Harbour' }).click();
    await expect.poll(async () => (await w.read()).map((r) => r.name)).toEqual(['Harbour']);
  } finally {
    await page.context().close();
  }
});

test('the command line takes a tool by name, places a place by a typed point and answers an unknown command', async ({
  browser,
}) => {
  const w = await world();
  await w.place('Harbour');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await expect(page.getByRole('form', { name: 'Command line' })).toBeHidden();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    const command = page.getByLabel('Command', { exact: true });
    const answer = page.locator('.map-command-answer');

    await command.fill('Line');
    await command.press('Enter');
    await expect(answer).toHaveText('Line is the tool.');
    await command.fill('Height brush');
    await command.press('Enter');
    await expect(answer).toContainText('Height brush is planned');
    await command.fill('dance');
    await command.press('Enter');
    await expect(answer).toContainText('not a command');

    await command.fill('PLACE Harbour 250,200');
    await command.press('Enter');
    await expect(answer).toContainText('Harbour is on the map at 250,200');
    const rows = await w.read();
    expect(rows.map((r) => r.name)).toEqual(['Harbour']);
    expect(geometryOf(rows[0]).parts[0]?.at).toEqual([250, 200]);

    await command.fill('UNDO');
    await command.press('Enter');
    await expect.poll(async () => (await w.read()).length).toBe(0);
    // The slash key goes to the line, and a letter typed there is not a tool key.
    await page.locator('.map-stage').click();
    await page.keyboard.press('/');
    await expect(command).toBeFocused();
    await page.keyboard.type('l');
    await expect(command).toHaveValue('l');
  } finally {
    await page.context().close();
  }
});

test('a spline is drawn through clicked and typed points, and changed by its points and its tension', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  type Curve = { shape: string; start?: number[]; segs?: number[][][]; closed?: boolean };
  const curve = async () => geometryOf((await w.read())[0]).parts[0] as Curve | undefined;
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    // By its key, as any tool; its one option is drawn with it.
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('s');
    await expect(page.getByRole('button', { name: 'Spline', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    const tension = page.getByRole('group', { name: 'Options of Spline' }).getByLabel('Tension');
    await expect(tension).toHaveValue('0.5');
    await page.getByLabel('Or make a new Location, named').fill('The curved lane');
    await page.getByRole('button', { name: 'Draw a new Location' }).click();
    // A point by pointer, two typed, the tension typed as a command, and DONE.
    await clickSheet(page, 0.2, 0.5);
    const command = page.getByLabel('Command', { exact: true });
    const answer = page.locator('.map-command-answer');
    await command.fill('400,200');
    await command.press('Enter');
    await expect(answer).toContainText('2 points');
    await command.fill('600,400');
    await command.press('Enter');
    await command.fill('TENSION 2');
    await command.press('Enter');
    await expect(answer).toHaveText('TENSION takes a number from 0 to 1.');
    await command.fill('TENSION 0');
    await command.press('Enter');
    await expect(answer).toHaveText('Tension is 0.');
    await expect(tension).toHaveValue('0');
    await command.fill('DONE');
    await command.press('Enter');
    await expect(page.getByRole('heading', { name: 'Change The curved lane' })).toBeVisible();
    // One open bezier part through the three points, its controls off the straight line.
    const drawn = await curve();
    expect(drawn?.shape).toBe('bezier');
    expect(drawn?.closed ?? false).toBe(false);
    expect(drawn?.segs?.map((seg) => seg[2])).toEqual([
      [400, 200],
      [600, 400],
    ]);
    const start = drawn?.start as number[];
    expect(drawn?.segs?.[0]?.[1]).toEqual([
      Math.round((400 - (600 - start[0]) / 6) * 100) / 100,
      Math.round((200 - (400 - start[1]) / 6) * 100) / 100,
    ]);
    // It is edited by its points, not "drawn with the API": a through-point by number.
    await expect(page.getByText(/it is drawn with the API/)).toHaveCount(0);
    await page.getByRole('group', { name: 'Point 2' }).getByLabel('y').fill('100');
    await page.getByRole('group', { name: 'Point 2' }).getByLabel('y').press('Tab');
    await expect.poll(async () => (await curve())?.segs?.[0]?.[2]).toEqual([400, 100]);
    // Its tension: at 1 every control lies on its end, so the curve is straight lines.
    const after = page.getByLabel('Tension (0 the roundest, 1 straight)');
    await expect(after).toHaveValue('0');
    await after.fill('1');
    await after.press('Tab');
    await expect.poll(async () => (await curve())?.segs?.[0]?.[0]).toEqual(start);
    expect((await curve())?.segs?.[1]).toEqual([
      [400, 100],
      [600, 400],
      [600, 400],
    ]);
    // A handle by drag moves a through-point; undo puts the curve back.
    const handle = page.locator('.m-ov-handle').nth(2);
    const at = await handle.boundingBox();
    if (!at) throw new Error('no handle');
    await page.mouse.move(at.x + at.width / 2, at.y + at.height / 2);
    await page.mouse.down();
    await page.mouse.move(at.x + at.width / 2 - 60, at.y + at.height / 2, { steps: 4 });
    await page.mouse.up();
    await expect.poll(async () => (await curve())?.segs?.[1]?.[2]?.[0]).toBeLessThan(600);
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect.poll(async () => (await curve())?.segs?.[1]?.[2]).toEqual([600, 400]);
  } finally {
    await page.context().close();
  }
});

test('a freehand stroke becomes a simplified line that is edited as any line', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  const line = async () => geometryOf((await w.read())[0]).parts[0];
  /** Press at a fraction of the sheet, drag through the others in small steps, and let go or not. */
  const drag = async (through: [number, number][], release = true) => {
    const box = await stageBox(page);
    if (!box) throw new Error('the map has no box');
    const at = (f: [number, number]) => [box.x + box.width * f[0], box.y + box.height * f[1]];
    const [x0, y0] = at(through[0] as [number, number]);
    await page.mouse.move(x0 as number, y0 as number);
    await page.mouse.down();
    for (const f of through.slice(1)) {
      const [x, y] = at(f);
      await page.mouse.move(x as number, y as number, { steps: 12 });
    }
    if (release) await page.mouse.up();
  };
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('f');
    await expect(page.getByRole('button', { name: 'Freehand', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    // Its option, and where the keyboard path is.
    await expect(
      page.getByRole('group', { name: 'Options of Freehand' }).getByLabel('Tolerance (pixels)'),
    ).toHaveValue('2');
    await page.getByLabel('Or make a new Location, named').fill('The goat path');
    await page.getByRole('button', { name: 'Draw a new Location' }).click();
    await expect(page.locator('.map-edit-panel')).toContainText(
      'The Line tool draws the same thing',
    );
    // A typed point has nowhere to go, and says where it does.
    const command = page.getByLabel('Command', { exact: true });
    await command.fill('100,100');
    await command.press('Enter');
    await expect(page.locator('.map-edit-bar')).toContainText('Freehand is drawn by dragging');

    // Escape while dragging drops the stroke: nothing is written.
    await page.locator('.map-stage svg').focus();
    await drag(
      [
        [0.3, 0.3],
        [0.5, 0.35],
      ],
      false,
    );
    await expect(page.locator('.m-ov-line')).toHaveCount(1);
    await page.keyboard.press('Escape');
    await page.mouse.up();
    await expect(page.locator('.map-edit-bar')).toContainText('The stroke was dropped.');
    expect(await w.read()).toHaveLength(0);

    // A stroke with two straight runs and a corner: many samples in, a few points out.
    await drag([
      [0.3, 0.3],
      [0.6, 0.3],
      [0.6, 0.6],
    ]);
    await expect(page.getByRole('heading', { name: 'Change The goat path' })).toBeVisible();
    const drawn = await line();
    expect(drawn?.shape).toBe('polyline');
    const pts = drawn?.pts ?? [];
    expect(pts.length).toBeGreaterThanOrEqual(3);
    expect(pts.length).toBeLessThanOrEqual(6);
    // The ends are where the stroke began and ended: the first run level, the second upright.
    const first = pts[0] as number[];
    const last = pts[pts.length - 1] as number[];
    expect(Math.abs((first[1] as number) - (pts[1]?.[1] as number))).toBeLessThan(8);
    expect((last[1] as number) - (first[1] as number)).toBeGreaterThan(100);
    expect((last[0] as number) - (first[0] as number)).toBeGreaterThan(100);
    // It is a line like any other: a point by number, then undo.
    await page.getByRole('group', { name: 'Point 1' }).getByLabel('x').fill('111');
    await page.getByRole('group', { name: 'Point 1' }).getByLabel('x').press('Tab');
    await expect.poll(async () => (await line())?.pts?.[0]?.[0]).toBe(111);
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect.poll(async () => (await line())?.pts?.[0]?.[0]).toBe(first[0]);
  } finally {
    await page.context().close();
  }
});

test('a height line needs a height and a unit, says them on the Map and keeps them when it is changed', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  type Valued = { shape: string; pts?: number[][]; value?: number; unit?: string };
  const line = async () => geometryOf((await w.read())[0]).parts[0] as Valued | undefined;
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('t');
    await expect(page.getByRole('button', { name: 'Height line', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    // Neither option has a value of its own: nothing is assumed.
    const options = page.getByRole('group', { name: 'Options of Height line' });
    await expect(options.getByLabel('Height')).toHaveValue('');
    await expect(options.getByLabel('Unit')).toHaveValue('');
    await page.getByLabel('Or make a new Location, named').fill('Ridge');
    await page.getByRole('button', { name: 'Draw a new Location' }).click();
    const command = page.getByLabel('Command', { exact: true });
    const answer = page.locator('.map-command-answer');
    for (const point of ['200,200', '500,200']) {
      await command.fill(point);
      await command.press('Enter');
    }
    // Without them the line is not written, and the draft is kept.
    await command.fill('DONE');
    await command.press('Enter');
    await expect(page.locator('.map-edit-bar')).toContainText(
      'A height line needs a height and a unit.',
    );
    expect(await w.read()).toHaveLength(0);
    await expect(page.locator('.m-ov-handle')).toHaveCount(2);
    // One in its field, one as a command.
    await options.getByLabel('Height').fill('250');
    await command.fill('UNIT m');
    await command.press('Enter');
    await expect(answer).toHaveText('Unit is m.');
    await expect(options.getByLabel('Unit')).toHaveValue('m');
    await command.fill('DONE');
    await command.press('Enter');
    await expect(page.getByRole('heading', { name: 'Change Ridge' })).toBeVisible();
    expect(await line()).toEqual({
      shape: 'polyline',
      pts: [
        [200, 200],
        [500, 200],
      ],
      value: 250,
      unit: 'm',
    });
    expect((await w.read())[0]?.role).toBe('isoline');
    // The Map says the height at the line, and in the mark's name.
    await expect(page.locator('.map-stage text.m-lbl-value')).toHaveText('250 m');
    await expect(
      page.locator('.map-stage').getByRole('button', { name: 'Ridge, height 250 m, isoline' }),
    ).toHaveCount(1);
    // A point moved keeps the height; the height itself is changed in the panel.
    await page.getByRole('group', { name: 'Point 1' }).getByLabel('x').fill('220');
    await page.getByRole('group', { name: 'Point 1' }).getByLabel('x').press('Tab');
    await expect.poll(async () => (await line())?.pts?.[0]?.[0]).toBe(220);
    expect(await line()).toMatchObject({ value: 250, unit: 'm' });
    const height = page.getByRole('group', { name: 'Height', exact: true });
    await height.getByLabel('Height').fill('300.5');
    await height.getByLabel('Height').press('Tab');
    await expect.poll(async () => (await line())?.value).toBe(300.5);
    await expect(page.locator('.map-stage text.m-lbl-value')).toHaveText('300.5 m');
    // One without the other is not written; both emptied takes the height away; undo brings it back.
    await height.getByLabel('Unit').fill('');
    await height.getByLabel('Unit').press('Tab');
    await expect(page.locator('.map-edit-bar')).toContainText('A height and its unit go together');
    expect(await line()).toMatchObject({ value: 300.5, unit: 'm' });
    await height.getByLabel('Height').fill('');
    await height.getByLabel('Height').press('Tab');
    await expect.poll(async () => (await line())?.value).toBeUndefined();
    await expect(page.locator('.map-stage text.m-lbl-value')).toHaveCount(0);
    await page.getByRole('button', { name: 'Undo' }).click();
    await expect.poll(async () => (await line())?.value).toBe(300.5);

    // The pair last drawn on this Map is offered the next time, in this browser.
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.locator('.map-stage svg').focus();
    await page.keyboard.press('t');
    const again = page.getByRole('group', { name: 'Options of Height line' });
    await expect(again.getByLabel('Height')).toHaveValue('250');
    await expect(again.getByLabel('Unit')).toHaveValue('m');
  } finally {
    await page.context().close();
  }
});

test('the Shortcuts dialog changes a tool key, refuses a taken one and puts the keys back', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await page.getByRole('button', { name: 'Shortcuts', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Shortcuts' });
    await expect(dialog).toBeVisible();

    // A key somebody else has is refused; a free one is taken.
    await dialog.getByRole('button', { name: 'Change the key of Line' }).click();
    await page.keyboard.press('p');
    await expect(dialog).toContainText("P is Pin's key");
    await dialog.getByRole('button', { name: 'Change the key of Line' }).click();
    await page.keyboard.press('q');
    await expect(dialog).toContainText('Line is now Q');
    await dialog.getByRole('button', { name: 'Close' }).click();

    // The new key picks the tool, the old one no longer does, and it is kept for the next visit.
    await page.locator('.map-stage').click();
    await page.keyboard.press('l');
    await expect(page.getByRole('button', { name: 'Line', exact: true })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    await page.keyboard.press('q');
    await expect(page.getByRole('button', { name: 'Line', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await page.reload();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    await expect(page.getByRole('button', { name: 'Line', exact: true })).toHaveAttribute(
      'aria-keyshortcuts',
      'Q',
    );

    await page.getByRole('button', { name: 'Shortcuts', exact: true }).click();
    await page.getByRole('button', { name: 'Put every key back' }).click();
    await expect(page.getByRole('button', { name: 'Line', exact: true })).toHaveAttribute(
      'aria-keyshortcuts',
      'L',
    );
  } finally {
    await page.context().close();
  }
});

test('the command line takes the points of a drawing, and DONE finishes it', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${w.chart.id}`);
    await expect(page.getByRole('heading', { name: 'Sword Coast', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit this map' }).click();
    const command = page.getByLabel('Command', { exact: true });
    const answer = page.locator('.map-command-answer');

    // No tool: a point has nowhere to go.
    await command.fill('10,10');
    await command.press('Enter');
    await expect(answer).toContainText('Choose a drawing tool first');

    await command.fill('Line');
    await command.press('Enter');
    await page.getByLabel('Or make a new Location, named').fill('Salt Road');
    await page.getByRole('button', { name: 'Draw a new Location' }).click();
    await command.fill('100,100');
    await command.press('Enter');
    await expect(answer).toContainText('1 point');
    await command.fill('300,150');
    await command.press('Enter');
    await expect(answer).toContainText('2 points');
    await command.fill('DONE');
    await command.press('Enter');
    await expect.poll(async () => (await w.read()).map((r) => r.name)).toEqual(['Salt Road']);
    const pts = geometryOf((await w.read())[0]).parts[0]?.pts;
    expect(pts).toEqual([
      [100, 100],
      [300, 150],
    ]);
  } finally {
    await page.context().close();
  }
});
