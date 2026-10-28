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

const F = 'lorenzo.map-system/1';
const SPHERE = { format: F, kind: 'sphere', extent: [-180, -90, 180, 90] };
const PLANE = { format: F, kind: 'plane', extent: [0, 0, 1000, 800] };
const GLOBE = { projection: { kind: 'orthographic', centre: [0, 0] } };

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
  const draw = (map: string, entry: string, parts: unknown[]) =>
    ok(
      gm.PUT('/tenants/{tenant_id}/maps/{map_id}/placements/{entry_id}', {
        params: { path: { ...path, map_id: map, entry_id: entry } },
        body: { geometry: { format: 'lorenzo.geometry/1', parts }, role: 'site', z: 0 },
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
  return { subject, gm, tenant, player, playerSubject, path, makeMap, place, draw, read };
}

type Geometry = { parts: { shape: string; at?: number[]; pts?: number[][] }[] };
const geometryOf = (row: { geometry: unknown } | undefined): Geometry =>
  (row?.geometry ?? { parts: [] }) as Geometry;

async function stageBox(page: Page) {
  const box = await page.locator('.map-stage').boundingBox();
  if (!box) throw new Error('the map has no box');
  return box;
}

/** A click at a fraction of the drawing. */
async function clickSheet(page: Page, fx: number, fy: number) {
  const box = await stageBox(page);
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
}

/** The longitude and latitude a flat sphere drawn whole has at a fraction of the drawing. */
async function lonLatAt(page: Page, fx: number, fy: number): Promise<[number, number]> {
  const box = await stageBox(page);
  const scale = Math.min(box.width / 360, box.height / 180);
  return [(fx * box.width - box.width / 2) / scale, -(fy * box.height - box.height / 2) / scale];
}

const marks = (page: Page, id: string) => page.locator(`.map-stage [data-entry="${id}"]`);
const limb = (page: Page) => page.locator('.map-stage circle.m-limb');
const gridPaths = (page: Page) => page.locator('.map-stage path.m-grid');

test('a writer makes a sphere with a radius and a globe projection, and it is saved as said', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/maps/?tenant=${w.tenant.id}`);
    await page.getByLabel('Name', { exact: true }).fill('Aeris');
    await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('sphere');
    // A sphere's sheet has no width or height to ask for.
    await expect(page.getByLabel('Width', { exact: true })).toBeHidden();
    await page.getByLabel("The world's radius (optional)").fill('6371');
    await page.getByLabel('Unit of the radius').fill('km');
    await page.getByRole('combobox', { name: 'The sphere is drawn' }).selectOption('orthographic');
    await page.getByLabel('The globe faces longitude').fill('10');
    await page.getByLabel('and latitude', { exact: true }).filter({ visible: true }).fill('20');
    await page.getByRole('button', { name: 'Make the Map' }).click();
    await expect(page.getByRole('heading', { name: 'Aeris', exact: true })).toBeVisible();
    await expect(limb(page)).toHaveCount(1);
    await expect(gridPaths(page)).toHaveCount(1);
    await expect(page.getByLabel('Grid', { exact: true })).toBeChecked();

    const made = await ok(w.gm.GET('/tenants/{tenant_id}/maps', { params: { path: w.path } }));
    const header = await ok(
      w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
        params: { path: { ...w.path, map_id: made.items[0]?.id ?? '' } },
      }),
    );
    expect(header.system).toMatchObject({
      kind: 'sphere',
      extent: [-180, -90, 180, 90],
      radius: { value: 6371, unit: 'km' },
    });
    expect(header.view).toEqual({ projection: { kind: 'orthographic', centre: [10, 20] } });
  } finally {
    await page.context().close();
  }
});

test('on a flat sphere the pointer says where it is and a writer draws a pin, a line and an area', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Aeris', SPHERE);
  await w.place('Port');
  await w.place('Road');
  await w.place('Marches');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Aeris', exact: true })).toBeVisible();
    await expect(limb(page)).toHaveCount(0);
    await expect(gridPaths(page)).toHaveCount(1);
    const box = await stageBox(page);
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await expect(page.locator('.map-cell')).toHaveText('0.0° N, 0.0° E');
    await page.mouse.move(box.x + box.width * 0.75, box.y + box.height * 0.25);
    await expect(page.locator('.map-cell')).toHaveText(/^\d+\.\d° N, \d+\.\d° E$/);

    await page.getByRole('button', { name: 'Edit this map' }).click();
    // A sphere draws no circle, no cells and snaps to nothing.
    for (const name of ['Circle', 'Cells']) {
      await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0);
    }
    await expect(page.getByLabel('Snap to the grid')).toHaveCount(0);

    const use = async (tool: string, name: string) => {
      await page.getByRole('button', { name: tool, exact: true }).click();
      await page.getByLabel('Find an entry by name').fill(name);
      await page
        .locator('.map-edit-panel')
        .getByRole('button', { name: new RegExp(`^${name} location$`) })
        .click();
    };
    await use('Pin', 'Port');
    await clickSheet(page, 0.75, 0.25);
    await expect.poll(async () => (await w.read(chart.id)).length).toBe(1);
    const [lon, lat] = await lonLatAt(page, 0.75, 0.25);
    const at = geometryOf((await w.read(chart.id))[0]).parts[0]?.at as [number, number];
    expect(Math.abs(at[0] - lon)).toBeLessThan(0.6);
    expect(Math.abs(at[1] - lat)).toBeLessThan(0.6);
    // A selected pin says where it is, and the fields are a longitude and a latitude.
    await expect(page.getByText(/^At \d+\.\d° N, \d+\.\d° E$/)).toBeVisible();
    const panel = page.locator('.map-edit-panel');
    await expect(panel.getByLabel('Longitude')).toHaveValue(String(at[0]));
    await expect(panel.getByLabel('Latitude')).toHaveValue(String(at[1]));

    await use('Line', 'Road');
    await clickSheet(page, 0.3, 0.3);
    await clickSheet(page, 0.4, 0.6);
    await page.keyboard.press('Enter');
    await expect.poll(async () => (await w.read(chart.id)).length).toBe(2);
    await use('Area', 'Marches');
    await clickSheet(page, 0.1, 0.4);
    await clickSheet(page, 0.2, 0.4);
    await clickSheet(page, 0.2, 0.5);
    await page.keyboard.press('Enter');
    await expect.poll(async () => (await w.read(chart.id)).length).toBe(3);
    const shapes = (await w.read(chart.id)).map((r) => geometryOf(r).parts[0]?.shape).sort();
    expect(shapes).toEqual(['point', 'polygon', 'polyline']);

    // A longitude beyond its range is refused where it is typed.
    await panel.getByLabel('Longitude').first().fill('200');
    await expect(panel.getByLabel('Longitude').first()).toHaveJSProperty(
      'validity.rangeOverflow',
      true,
    );
  } finally {
    await page.context().close();
  }
});

test('a reader turns a globe, changes how it is drawn for themselves and goes back to the saved view', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Aeris', SPHERE, GLOBE);
  const near = await w.place('Near');
  const far = await w.place('Far');
  await w.draw(chart.id, near.id, [{ shape: 'point', at: [10, 20] }]);
  await w.draw(chart.id, far.id, [{ shape: 'point', at: [170, 0] }]);
  const page = await signedIn(browser, w.playerSubject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Aeris', exact: true })).toBeVisible();
    await expect(limb(page)).toHaveCount(1);
    await expect(marks(page, near.id).first()).toBeVisible();
    // The far side of the globe draws nothing, and the list still names it.
    await expect(marks(page, far.id)).toHaveCount(0);
    await expect(page.getByRole('button', { name: /^Far/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Edit this map' })).toHaveCount(0);

    // Turn east until the far place faces us.
    for (let i = 0; i < 12; i += 1) await page.getByRole('button', { name: 'Turn east' }).click();
    await expect(marks(page, far.id).first()).toBeVisible();
    await expect(marks(page, near.id)).toHaveCount(0);
    // Back to the saved view.
    await page.getByRole('button', { name: 'Back to the saved view' }).click();
    await expect(marks(page, near.id).first()).toBeVisible();
    await expect(marks(page, far.id)).toHaveCount(0);

    // A flat view of the same Map is the reader's own, kept across a reload, and shows both.
    await page.getByRole('combobox', { name: 'Drawn as' }).selectOption('equirectangular');
    await expect(limb(page)).toHaveCount(0);
    await expect(marks(page, far.id).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Turn east' })).toBeHidden();
    await page.reload();
    await expect(page.getByRole('combobox', { name: 'Drawn as' })).toHaveValue('equirectangular');
    await expect(marks(page, near.id).first()).toBeVisible();
    // The Map itself was never changed.
    const header = await ok(
      w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
        params: { path: { ...w.path, map_id: chart.id } },
      }),
    );
    expect(header.view).toEqual(GLOBE);
    // And Mercator draws both as well.
    await page.getByRole('combobox', { name: 'Drawn as' }).selectOption('mercator');
    await expect(marks(page, far.id).first()).toBeVisible();
    await expect(marks(page, near.id).first()).toBeVisible();
  } finally {
    await page.context().close();
  }
});

test('a sphere with places cannot become a plane, and the form keeps the draft', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Aeris', SPHERE);
  const one = await w.place('One');
  await w.draw(chart.id, one.id, [{ shape: 'point', at: [10, 10] }]);
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Aeris', exact: true })).toBeVisible();
    await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('plane');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect(page.getByText(/cannot become a sphere, or stop being one/)).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'The sheet is' })).toHaveValue('plane');
    // What is only said or drawn may change under places.
    await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('sphere');
    await page.getByRole('combobox', { name: 'The sphere is drawn' }).selectOption('mercator');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect
      .poll(
        async () =>
          (
            await ok(
              w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
                params: { path: { ...w.path, map_id: chart.id } },
              }),
            )
          ).view,
      )
      .toEqual({ projection: { kind: 'mercator' } });
    expect(PLANE.kind).toBe('plane');
  } finally {
    await page.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`a sphere, flat and round, has no accessibility errors in ${theme}`, async ({ browser }) => {
    const w = await world();
    const chart = await w.makeMap('Aeris', SPHERE, GLOBE);
    const near = await w.place('Near');
    await w.draw(chart.id, near.id, [{ shape: 'point', at: [10, 20] }]);
    const page = await signedIn(browser, w.subject, theme);
    try {
      await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
      await expect(page.getByRole('heading', { name: 'Aeris', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Edit this map' }).click();
      const round = await new AxeBuilder({ page }).analyze();
      expect(round.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.getByRole('combobox', { name: 'Drawn as' }).selectOption('equirectangular');
      const flat = await new AxeBuilder({ page }).analyze();
      expect(flat.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await page.goto(`/maps/?tenant=${w.tenant.id}`);
      await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('sphere');
      const form = await new AxeBuilder({ page }).analyze();
      expect(form.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}
