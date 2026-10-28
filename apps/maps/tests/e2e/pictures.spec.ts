import { randomUUID } from 'node:crypto';
import { deflateSync } from 'node:zlib';
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
const PLANE = { format: F, kind: 'plane', extent: [0, 0, 1000, 800] };
const SPHERE = { format: F, kind: 'sphere', extent: [-180, -90, 180, 90] };

const CRC = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return (bytes: Buffer) => {
    let c = 0xffffffff;
    for (const byte of bytes) c = (table[(c ^ byte) & 0xff] as number) ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
})();

/** A valid PNG of one colour, so a browser decodes it. */
function png(r: number, g: number, b: number, width = 4, height = 4): Buffer {
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type), data]);
    const out = Buffer.alloc(8 + data.length + 4);
    out.writeUInt32BE(data.length, 0);
    body.copy(out, 4);
    out.writeUInt32BE(CRC(body), 8 + data.length);
    return out;
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  const row = Buffer.concat([Buffer.from([0]), Buffer.from(Array(width).fill([r, g, b]).flat())]);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', header),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

const SVG = Buffer.from(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20"><rect width="40" height="20" fill="#2468"/></svg>',
);
const BAD_SVG = Buffer.from(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><script>alert(1)</script></svg>',
);

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
  const makeMap = (name: string, system: Record<string, unknown>) =>
    ok(
      gm.POST('/tenants/{tenant_id}/maps', {
        params: { path },
        body: { name, system, is_public: true },
      }),
    );
  const header = (map: string) =>
    ok(
      gm.GET('/tenants/{tenant_id}/maps/{map_id}', {
        params: { path: { ...path, map_id: map } },
        cache: 'no-cache',
      }),
    );
  const information = async (map: string) =>
    (
      await ok(
        gm.GET('/tenants/{tenant_id}/entities/{entity_id}/information', {
          params: { path: { ...path, entity_id: map } },
        }),
      )
    ).items;
  return { subject, gm, tenant, playerSubject, path, makeMap, header, information };
}

const pictures = (page: Page) => page.locator('.map-stage image.m-layer');

/** Adds a picture through the Pictures section. */
async function addPicture(
  page: Page,
  file: { name: string; mimeType: string; buffer: Buffer },
  title: string,
  open = true,
) {
  await page.getByLabel('A picture', { exact: true }).setInputFiles(file);
  await page.getByLabel('What it is called').fill(title);
  const everyone = page.getByLabel('Everyone in the library may see it').last();
  if (open) await everyone.check();
  else await everyone.uncheck();
  await page.getByRole('button', { name: 'Add the picture' }).click();
}

test('a writer adds a picture, sets it by two points, orders two and reviews a replaced one', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Coast', PLANE);
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Coast', exact: true })).toBeVisible();
    await expect(pictures(page)).toHaveCount(0);
    await addPicture(
      page,
      { name: 'sea.png', mimeType: 'image/png', buffer: png(30, 90, 160) },
      'Sea',
    );
    // The page is drawn again with the picture under the sheet's marks.
    await expect(pictures(page)).toHaveCount(1);
    await expect(pictures(page).first()).toHaveAttribute('href', /^data:image\/png;base64,/);
    const layers = (await w.header(chart.id)).layers ?? [];
    expect(layers).toHaveLength(1);
    expect(layers[0]).toMatchObject({
      title: 'Sea',
      content_type: 'image/png',
      needs_review: false,
    });
    await expect(page.getByLabel('Pictures', { exact: true })).toBeChecked();

    // Fit the sheet first: the picture is square, the sheet is 1000 by 800, so it is 800 wide.
    const fitted = await pictures(page).first().getAttribute('transform');
    const [a0, , , d0] = (fitted ?? '')
      .replace(/matrix\(|\)/g, '')
      .split(' ')
      .map(Number);
    expect(a0).toBeCloseTo(d0 as number, 4);

    // Set by two points: the picture's top edge from (100, 100) to (500, 100).
    const box = page.locator('fieldset', { hasText: 'Sea' }).first();
    await box.getByRole('combobox', { name: 'Where it lies' }).selectOption('two');
    const first = box.locator('fieldset', { hasText: 'Point A' });
    await first.getByLabel('Across the picture (%)').fill('0');
    await first.getByLabel('Down the picture (%)').fill('0');
    await first.getByLabel('On the sheet, x').fill('100');
    await first.getByLabel('On the sheet, y').fill('100');
    const second = box.locator('fieldset', { hasText: 'Point B' });
    await second.getByLabel('Across the picture (%)').fill('100');
    await second.getByLabel('Down the picture (%)').fill('0');
    await second.getByLabel('On the sheet, x').fill('500');
    await second.getByLabel('On the sheet, y').fill('100');
    await box.getByLabel('Opacity (%)').fill('60');
    await box.getByRole('button', { name: 'Save this picture' }).click();
    await expect
      .poll(async () => ((await w.header(chart.id)).layers ?? [])[0]?.calibration)
      .toEqual({
        anchors: [
          { image: [0, 0], at: [100, 100] },
          { image: [1, 0], at: [500, 100] },
        ],
      });
    expect(((await w.header(chart.id)).layers ?? [])[0]?.opacity).toBeCloseTo(0.6, 5);
    // The matrix is a turn-free scale: a and d equal, b and c zero, and 400 units over 4 pixels.
    await expect(pictures(page)).toHaveAttribute('opacity', '0.6');
    const moved = (await pictures(page).first().getAttribute('transform')) ?? '';
    const [a, b, c, d] = moved
      .replace(/matrix\(|\)/g, '')
      .split(' ')
      .map(Number);
    expect(Math.abs(b as number)).toBeLessThan(1e-6);
    expect(Math.abs(c as number)).toBeLessThan(1e-6);
    expect(a).toBeCloseTo(d as number, 4);
    expect(a).not.toBeCloseTo(a0 as number, 2);

    // A second picture goes on top; moving it up puts it first.
    await addPicture(
      page,
      { name: 'roads.png', mimeType: 'image/png', buffer: png(200, 160, 40) },
      'Roads',
    );
    await expect(pictures(page)).toHaveCount(2);
    let titles = ((await w.header(chart.id)).layers ?? []).map((l) => l.title);
    expect(titles).toEqual(['Sea', 'Roads']);
    await page
      .locator('fieldset', { hasText: 'Roads' })
      .first()
      .getByRole('button', { name: 'Move up' })
      .click();
    await expect
      .poll(async () => ((await w.header(chart.id)).layers ?? []).map((l) => l.title))
      .toEqual(['Roads', 'Sea']);
    titles = ((await w.header(chart.id)).layers ?? []).map((l) => l.title);

    // Replacing a picture raises "needs review" until it is marked reviewed.
    const roads = page.locator('fieldset', { hasText: 'Roads' }).first();
    await roads
      .getByLabel('Replace the picture')
      .setInputFiles({ name: 'roads2.png', mimeType: 'image/png', buffer: png(10, 10, 10) });
    await roads.getByRole('button', { name: 'Replace', exact: true }).click();
    await expect(page.getByText(/replaced after it was set up/).first()).toBeVisible();
    expect(
      ((await w.header(chart.id)).layers ?? []).find((l) => l.title === 'Roads')?.needs_review,
    ).toBe(true);
    await page
      .locator('fieldset', { hasText: 'Roads' })
      .first()
      .getByRole('button', { name: 'Mark reviewed' })
      .click();
    await expect
      .poll(
        async () =>
          ((await w.header(chart.id)).layers ?? []).find((l) => l.title === 'Roads')?.needs_review,
      )
      .toBe(false);

    // Removing one takes the layer and its Information.
    const sea = page.locator('fieldset', { hasText: 'Sea' }).first();
    await sea.getByRole('button', { name: 'Remove' }).click();
    await sea.getByRole('button', { name: /^Really remove/ }).click();
    await expect
      .poll(async () => ((await w.header(chart.id)).layers ?? []).map((l) => l.title))
      .toEqual(['Roads']);
    // The Information goes in the request after the layer's, so it is waited for as well.
    await expect
      .poll(async () => (await w.information(chart.id)).map((i) => i.title))
      .toEqual(['Roads']);
    expect(titles).toHaveLength(2);
  } finally {
    await page.context().close();
  }
});

test('an SVG is a picture when it passes the lint, and a refused one leaves nothing behind', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Coast', PLANE);
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Coast', exact: true })).toBeVisible();
    await addPicture(page, { name: 'bad.svg', mimeType: 'image/svg+xml', buffer: BAD_SVG }, 'Bad');
    await expect(page.getByText(/element that a picture may not/)).toBeVisible();
    await expect(pictures(page)).toHaveCount(0);
    expect(await w.information(chart.id)).toHaveLength(0);
    // The same form takes a clean one.
    await page.getByLabel('A picture', { exact: true }).setInputFiles({
      name: 'sea.svg',
      mimeType: 'image/svg+xml',
      buffer: SVG,
    });
    await page.getByLabel('What it is called').fill('Sea');
    await page.getByRole('button', { name: 'Add the picture' }).click();
    await expect(pictures(page)).toHaveCount(1);
    await expect(pictures(page).first()).toHaveAttribute('href', /^data:image\/svg\+xml;base64,/);
    // A 40 x 20 viewBox is drawn at its own proportions, two to one.
    const matrix = ((await pictures(page).first().getAttribute('transform')) ?? '')
      .replace(/matrix\(|\)/g, '')
      .split(' ')
      .map(Number);
    expect(matrix[0]).toBeCloseTo(matrix[3] as number, 4);
    await expect(pictures(page).first()).toHaveAttribute('width', '40');
    await expect(pictures(page).first()).toHaveAttribute('height', '20');
  } finally {
    await page.context().close();
  }
});

test('a player sees a picture whose Information is open to them, and can hide it', async ({
  browser,
}) => {
  const w = await world();
  const chart = await w.makeMap('Coast', PLANE);
  const gmPage = await signedIn(browser, w.subject);
  try {
    await gmPage.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await addPicture(
      gmPage,
      { name: 'open.png', mimeType: 'image/png', buffer: png(1, 2, 3) },
      'Open',
      true,
    );
    await expect(pictures(gmPage)).toHaveCount(1);
    await addPicture(
      gmPage,
      { name: 'secret.png', mimeType: 'image/png', buffer: png(9, 9, 9) },
      'Secret',
      false,
    );
    await expect(pictures(gmPage)).toHaveCount(2);
  } finally {
    await gmPage.context().close();
  }
  const page = await signedIn(browser, w.playerSubject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Coast', exact: true })).toBeVisible();
    // Only the open one is read; the other is not even said to exist.
    await expect(pictures(page)).toHaveCount(1);
    const toggle = page.getByLabel('Pictures', { exact: true });
    await expect(toggle).toBeChecked();
    await toggle.uncheck();
    await expect(pictures(page)).toHaveCount(0);
    await toggle.check();
    await expect(pictures(page)).toHaveCount(1);
    await expect(page.getByRole('heading', { name: 'Settings' })).toHaveCount(0);
    expect(((await w.header(chart.id)).layers ?? []).map((l) => l.title).sort()).toEqual([
      'Open',
      'Secret',
    ]);
  } finally {
    await page.context().close();
  }
});

test('a sphere offers no pictures', async ({ browser }) => {
  const w = await world();
  const chart = await w.makeMap('Aeris', SPHERE);
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
    await expect(page.getByRole('heading', { name: 'Aeris', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Pictures' })).toHaveCount(0);
  } finally {
    await page.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`a Map with a picture and its Pictures section has no accessibility errors in ${theme}`, async ({
    browser,
  }) => {
    const w = await world();
    const chart = await w.makeMap('Coast', PLANE);
    const page = await signedIn(browser, w.subject, theme);
    try {
      await page.goto(`/map/?tenant=${w.tenant.id}&id=${chart.id}`);
      await expect(page.getByRole('heading', { name: 'Coast', exact: true })).toBeVisible();
      await addPicture(
        page,
        { name: 'sea.png', mimeType: 'image/png', buffer: png(30, 90, 160) },
        'Sea',
      );
      await expect(pictures(page)).toHaveCount(1);
      await page
        .locator('fieldset', { hasText: 'Sea' })
        .first()
        .getByRole('combobox', { name: 'Where it lies' })
        .selectOption('two');
      const result = await new AxeBuilder({ page }).analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}
