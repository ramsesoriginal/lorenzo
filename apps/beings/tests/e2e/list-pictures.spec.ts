import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import type { World } from './support/world.ts';

const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
);

async function portrait(world: World, id: string, isPublic = true) {
  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/picture', {
      params: {
        path: { tenant_id: world.tenantId, entity_id: id },
        query: { is_public: isPublic },
      },
      body: { file: 'portrait.png' },
      bodySerializer() {
        const data = new FormData();
        data.append('file', new File([PNG], 'portrait.png', { type: 'image/png' }));
        return data;
      },
    }),
  );
}

test('80px portraits and a live desktop preview follow the hovered row', async ({ world, as }) => {
  await portrait(world, world.pia.character.entity_id);
  await portrait(world, world.oskar.character.entity_id);
  const page = await as(world.gm);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  const ash = page.locator('[data-list] > li').filter({ hasText: 'Ashfang' });
  const brisk = page.locator('[data-list] > li').filter({ hasText: 'Brisk' });
  const thumbnail = ash.locator('[data-list-picture]');
  await expect(thumbnail).toBeVisible();
  expect(
    await thumbnail.evaluate((image) => {
      const rect = image.getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    }),
  ).toEqual({ width: 80, height: 80 });
  const popup = page.locator('[data-picture-preview]');
  await expect(popup).toBeHidden();
  await ash.hover();
  await expect(popup).toBeVisible();
  await expect(popup.locator('img')).toHaveAttribute('alt', 'Picture of Ashfang');
  await expect(popup.locator('img')).toHaveAttribute(
    'src',
    (await thumbnail.getAttribute('src')) ?? '',
  );
  const at = await popup.boundingBox();
  const viewport = page.viewportSize();
  expect(at?.width).toBe(512);
  expect(at?.height).toBe(512);
  expect(at?.x).toBeGreaterThanOrEqual(0);
  expect((at?.x ?? 0) + (at?.width ?? 0)).toBeLessThanOrEqual(viewport?.width ?? 0);
  expect((at?.y ?? 0) + (at?.height ?? 0)).toBeLessThanOrEqual(viewport?.height ?? 0);
  await brisk.hover();
  await expect(popup.locator('img')).toHaveAttribute('alt', 'Picture of Brisk');
  await page.keyboard.press('Escape');
  await expect(popup).toBeHidden();
  await ash.getByRole('link').focus();
  await expect(popup).toBeVisible();
  await page.getByRole('searchbox', { name: 'Search' }).fill('Brisk');
  await expect(popup).toBeHidden();
  await expect(ash).toHaveCount(0);
  await brisk.getByRole('link').click();
  await expect(page.getByRole('heading', { name: 'Brisk', level: 1 })).toBeVisible();
});

test('a picture hidden from the viewer is neither shown nor downloaded', async ({ world, as }) => {
  await portrait(world, world.pia.character.entity_id, false);
  const page = await as(world.oskar);
  const downloads: string[] = [];
  page.on('request', (request) => {
    if (/\/payloads\/[^/]+\/content/.test(request.url())) downloads.push(request.url());
  });
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  const row = page.locator('[data-list] > li').filter({ hasText: 'Ashfang' });
  await expect(row).toHaveAttribute('data-picture-state', 'none');
  await expect(row.locator('[data-list-picture]')).toBeHidden();
  await row.hover();
  await expect(page.locator('[data-picture-preview]')).toBeHidden();
  expect(downloads).toEqual([]);
});

test('late pictures do not open a popup after the pointer leaves', async ({ world, as }) => {
  await portrait(world, world.pia.character.entity_id);
  const page = await as(world.gm);
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(`**/entities/${world.pia.character.entity_id}/preview`, async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  const row = page.locator('[data-list] > li').filter({ hasText: 'Ashfang' });
  await row.hover();
  await page.mouse.move(0, 0);
  release();
  await expect(row.locator('[data-list-picture]')).toBeVisible();
  await expect(page.locator('[data-picture-preview]')).toBeHidden();
});

test('touch devices get portraits without a popup or an intercepted tap', async ({
  world,
  as,
  browser,
}) => {
  await portrait(world, world.pia.character.entity_id);
  const signedIn = await as(world.gm);
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    storageState: await signedIn.context().storageState(),
  });
  try {
    const page = await context.newPage();
    await page.goto(`/beings/?tenant=${world.tenantId}`);
    const row = page.locator('[data-list] > li').filter({ hasText: 'Ashfang' });
    await expect(row.locator('[data-list-picture]')).toBeVisible();
    await row.getByRole('link').focus();
    await row.dispatchEvent('pointerenter', { pointerType: 'touch' });
    await expect(page.locator('[data-picture-preview]')).toBeHidden();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await row.getByRole('link').tap();
    await expect(page.getByRole('heading', { name: 'Ashfang', level: 1 })).toBeVisible();
  } finally {
    await context.close();
  }
});
