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
const SCALED = {
  format: F,
  kind: 'plane',
  extent: [0, 0, 1000, 800],
  scale: { per_unit: 0.5, unit: 'miles' },
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
  const makeMap = (name: string, system: Record<string, unknown>) =>
    ok(
      gm.POST('/tenants/{tenant_id}/maps', {
        params: { path },
        body: { name, system, is_public: true },
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
  const miles = async () => {
    const group = await ok(
      gm.POST('/tenants/{tenant_id}/stat-groups', {
        params: { path },
        body: { name: 'Travel', priority: 0, mandatory: false },
      }),
    );
    return ok(
      gm.POST('/tenants/{tenant_id}/stat-definitions', {
        params: { path },
        body: {
          name: 'Miles',
          stat_group_id: group.id,
          value_type: 'float',
          unit: 'miles',
          adjustable_in_play: false,
          pin: false,
          signed: false,
        },
      }),
    );
  };
  const join = async (
    end_a: string,
    end_b: string,
    name: string,
    length?: number,
    stat?: string,
  ) => {
    const made = await ok(
      gm.POST('/tenants/{tenant_id}/connections', {
        params: { path },
        body: { name, end_a, end_b, one_way: false, prototypes: [], is_public: true },
      }),
    );
    if (length !== undefined && stat) {
      await ok(
        gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
          params: { path: { ...path, entity_id: made.id, stat_definition_id: stat } },
          body: { value: length, acquire_group: false },
        }),
      );
    }
    return made;
  };
  return { subject, gm, tenant, playerSubject, path, place, makeMap, draw, miles, join };
}

const onMap = (tenant: string, id: string) => `/map/?tenant=${tenant}&id=${id}`;

async function measure(page: Page, from: string, to: string, stat?: string) {
  await page.getByLabel('Measure from').selectOption({ label: from });
  await page.getByLabel('Measure to').selectOption({ label: to });
  if (stat) await page.getByLabel('By the connections, measured in').selectOption({ label: stat });
  await page.getByRole('button', { name: 'Measure', exact: true }).click();
}

test('a writer sets how a grid counts diagonals and reads the straight line between two places', async ({
  browser,
}) => {
  const w = await world();
  const keep = await w.place('Keep');
  const marsh = await w.place('Marsh');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/maps/?tenant=${w.tenant.id}`);
    await page.getByLabel('Name', { exact: true }).fill('Battle grid');
    await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('square');
    await page.getByLabel('Cell size').filter({ visible: true }).fill('50');
    await page.getByLabel('One cell is').fill('5');
    await page.getByLabel('of (a unit)').fill('feet');
    await page.getByLabel('Diagonals count as').selectOption('chebyshev');
    await page.getByRole('button', { name: 'Make the Map' }).click();
    await expect(page.getByRole('heading', { name: 'Battle grid', exact: true })).toBeVisible();
    const made = (
      await ok(w.gm.GET('/tenants/{tenant_id}/maps', { params: { path: w.path } }))
    ).items.find((m) => m.name === 'Battle grid');
    if (!made) throw new Error('the Map was not made');
    const header = await ok(
      w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
        params: { path: { ...w.path, map_id: made.id } },
      }),
    );
    expect(header.system).toMatchObject({ kind: 'square', metric: 'chebyshev' });

    await w.draw(made.id, keep.id, [25, 25]);
    await w.draw(made.id, marsh.id, [175, 125]);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Distance' })).toBeVisible();
    await measure(page, 'Keep', 'Marsh');
    await expect(
      page.getByText('Straight line: 15 feet, counting diagonals by the chebyshev rule.'),
    ).toBeVisible();
    // The same place twice is nothing, and says so.
    await measure(page, 'Keep', 'Keep');
    await expect(page.getByText(/^Straight line: 0 feet/)).toBeVisible();

    // The way of counting is set again in Settings and read at once.
    await page.getByLabel('Diagonals count as').selectOption('manhattan');
    await page.getByRole('button', { name: 'Save settings' }).click();
    await expect
      .poll(
        async () =>
          (
            await ok(
              w.gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
                params: { path: { ...w.path, map_id: made.id } },
              }),
            )
          ).system,
      )
      .toMatchObject({ metric: 'manhattan' });
    await page.reload();
    await measure(page, 'Keep', 'Marsh');
    await expect(
      page.getByText('Straight line: 25 feet, counting diagonals by the manhattan rule.'),
    ).toBeVisible();

    // A hex has one way to count: no choice is offered.
    await page.goto(`/maps/?tenant=${w.tenant.id}`);
    await page.getByRole('combobox', { name: 'The sheet is' }).selectOption('hex');
    await expect(page.getByLabel('Diagonals count as')).toBeHidden();
  } finally {
    await page.context().close();
  }
});

test('a Map says what it measures, by the straight line and by the connections', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Scaled', SCALED);
  const bare = await w.makeMap('Bare', { format: F, kind: 'plane', extent: [0, 0, 1000, 800] });
  const a = await w.place('Hollowmere');
  const b = await w.place('Dunmere');
  const c = await w.place('Brindle');
  const d = await w.place('Island');
  for (const map of [chart.id, bare.id]) {
    await w.draw(map, a.id, [0, 0]);
    await w.draw(map, b.id, [300, 400]);
    await w.draw(map, c.id, [600, 400]);
    await w.draw(map, d.id, [900, 700]);
  }
  const miles = await w.miles();
  await w.join(a.id, b.id, 'First road', 12.5, miles.id);
  await w.join(b.id, c.id, 'Second road', 5.5, miles.id);
  await w.join(c.id, d.id, 'Rough track');
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(onMap(w.tenant.id, chart.id));
    await expect(page.getByRole('heading', { name: 'Scaled', exact: true })).toBeVisible();

    await measure(page, 'Hollowmere', 'Dunmere', 'Miles (miles)');
    await expect(page.getByText('Straight line: 250 miles.')).toBeVisible();
    await expect(page.getByText('By the connections: 12.5 miles, over 1 leg.')).toBeVisible();
    await expect(page.getByText('First road, Hollowmere to Dunmere: 12.5 miles')).toBeVisible();

    await measure(page, 'Hollowmere', 'Brindle', 'Miles (miles)');
    await expect(page.getByText('By the connections: 18 miles, over 2 legs.')).toBeVisible();

    // A leg with no length makes the answer a lower bound, never a number.
    await measure(page, 'Hollowmere', 'Island', 'Miles (miles)');
    await expect(
      page.getByText('By the connections: at least 18 miles; 1 of 3 legs have no length.'),
    ).toBeVisible();
    await expect(page.getByText('Rough track, Brindle to Island: no length')).toBeVisible();

    // Without a stat only the straight line is asked for.
    await measure(page, 'Dunmere', 'Brindle', 'Not by the connections');
    await expect(page.getByText('Straight line: 150 miles.')).toBeVisible();
    await expect(page.getByText(/^By the connections:/)).toHaveCount(0);

    // A Map with no scale says so rather than answering zero.
    await page.goto(onMap(w.tenant.id, bare.id));
    await expect(page.getByRole('heading', { name: 'Bare', exact: true })).toBeVisible();
    await measure(page, 'Hollowmere', 'Dunmere');
    await expect(page.getByText('Straight line: the Map has no scale.')).toBeVisible();
  } finally {
    await page.context().close();
  }
});

test('two places with no connection between them say there is no known route', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Scaled', SCALED);
  const a = await w.place('Hollowmere');
  const b = await w.place('Dunmere');
  await w.draw(chart.id, a.id, [0, 0]);
  await w.draw(chart.id, b.id, [300, 400]);
  await w.miles();
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(onMap(w.tenant.id, chart.id));
    await measure(page, 'Hollowmere', 'Dunmere', 'Miles (miles)');
    await expect(page.getByText('Straight line: 250 miles.')).toBeVisible();
    await expect(page.getByText('By the connections: no known route.')).toBeVisible();
    // Nothing is chosen yet.
    await page.reload();
    await page.getByRole('button', { name: 'Measure', exact: true }).click();
    await expect(page.getByText('Choose the two places to measure between.')).toBeVisible();
  } finally {
    await page.context().close();
  }
});

test('a player measures too, and has no setting to change', async ({ browser }) => {
  const w = await world();
  const chart = await w.makeMap('Scaled', SCALED);
  const a = await w.place('Hollowmere');
  const b = await w.place('Dunmere');
  await w.draw(chart.id, a.id, [0, 0]);
  await w.draw(chart.id, b.id, [300, 400]);
  const page = await signedIn(browser, w.playerSubject);
  try {
    await page.goto(onMap(w.tenant.id, chart.id));
    await measure(page, 'Hollowmere', 'Dunmere');
    await expect(page.getByText('Straight line: 250 miles.')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Settings' })).toHaveCount(0);
  } finally {
    await page.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`the Distance section and its answer have no accessibility errors in ${theme}`, async ({
    browser,
  }) => {
    const w = await world();
    const chart = await w.makeMap('Scaled', SCALED);
    const a = await w.place('Hollowmere');
    const b = await w.place('Dunmere');
    await w.draw(chart.id, a.id, [0, 0]);
    await w.draw(chart.id, b.id, [300, 400]);
    const miles = await w.miles();
    await w.join(a.id, b.id, 'First road', 12.5, miles.id);
    const page = await signedIn(browser, w.subject, theme);
    try {
      await page.goto(onMap(w.tenant.id, chart.id));
      await expect(page.getByRole('heading', { name: 'Distance' })).toBeVisible();
      const before = await new AxeBuilder({ page }).analyze();
      expect(before.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await measure(page, 'Hollowmere', 'Dunmere', 'Miles (miles)');
      await expect(page.getByText('By the connections: 12.5 miles, over 1 leg.')).toBeVisible();
      const after = await new AxeBuilder({ page }).analyze();
      expect(after.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}
