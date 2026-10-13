// The card a link to an entity opens when pointed at (ADR 0264), against the real API: on hover, on
// keyboard focus, on a tap, and what it holds for who is reading.
import type { Page } from '@playwright/test';
import { ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';
import { expect, test } from './support/fixtures.ts';
import { DESCRIPTIONS } from './support/scenes.ts';
import type { World } from './support/world.ts';

/** A Backpack whose description links to a Belt Pouch that has a description and a weight. */
async function scene(world: World) {
  const pouch = await world.item('Belt Pouch');
  await world.slug(pouch, 'belt-pouch');
  await world.describe(pouch, DESCRIPTIONS.pouch);
  await world.setStat(pouch, 'weight', 2);
  const backpack = await world.item('Backpack');
  await world.describe(backpack, DESCRIPTIONS.backpack);
  return { pouch, backpack };
}

const link = (page: Page) =>
  page.locator('[data-item-view]').getByRole('link', { name: 'Belt Pouch' });
const card = (page: Page) => page.getByRole('tooltip');

test('hovering a link shows the entry, and moving away puts the card away', async ({
  world,
  as,
}) => {
  const { backpack } = await scene(world);
  const page = await as(world.pia);
  await page.goto(`/item/?tenant=${world.tenantId}&id=${backpack}`);

  await link(page).hover();
  await expect(card(page)).toContainText('Belt Pouch');
  await expect(card(page)).toContainText('Item');
  await expect(card(page)).toContainText('weight 2');
  await expect(card(page)).toContainText('A small pouch worn at the hip');
  await expect(link(page)).toHaveAttribute('aria-describedby', 'link-preview');

  await page.getByRole('heading', { level: 1 }).hover();
  await expect(card(page)).toBeHidden();
});

test('the card is cached for the page: a second hover asks the API nothing', async ({
  world,
  as,
}) => {
  const { backpack } = await scene(world);
  const page = await as(world.pia);
  await page.goto(`/item/?tenant=${world.tenantId}&id=${backpack}`);
  const asked: string[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/preview')) asked.push(request.url());
  });

  await link(page).hover();
  await expect(card(page)).toBeVisible();
  await page.getByRole('heading', { level: 1 }).hover();
  await expect(card(page)).toBeHidden();
  await link(page).hover();
  await expect(card(page)).toBeVisible();

  expect(asked).toHaveLength(1);
});

test('keyboard focus shows the card and Escape puts it away', async ({ world, as }) => {
  const { backpack } = await scene(world);
  const page = await as(world.pia);
  await page.goto(`/item/?tenant=${world.tenantId}&id=${backpack}`);

  await link(page).focus();
  await expect(card(page)).toContainText('Belt Pouch');

  await page.keyboard.press('Escape');
  await expect(card(page)).toBeHidden();
  // Still focused, and following it is unchanged.
  await expect(link(page)).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1, name: 'Belt Pouch' })).toBeVisible();
});

test('a tap shows the card and a second tap follows the link', async ({ world, browser }) => {
  const { backpack } = await scene(world);
  const context = await browser.newContext({
    hasTouch: true,
    storageState: {
      cookies: [],
      origins: [
        {
          origin: new URL(SITE_URL).origin,
          localStorage: [
            { name: REFRESH_TOKEN_KEY, value: await refreshTokenFor(world.pia.subject) },
          ],
        },
      ],
    },
  });
  try {
    const page = await context.newPage();
    await page.goto(`/item/?tenant=${world.tenantId}&id=${backpack}`);

    await link(page).tap();
    await expect(card(page)).toContainText('Belt Pouch');
    await expect(page.getByRole('heading', { level: 1, name: 'Backpack' })).toBeVisible();

    await link(page).tap();
    await expect(page.getByRole('heading', { level: 1, name: 'Belt Pouch' })).toBeVisible();
  } finally {
    await context.close();
  }
});

test('the card shows no description a player may not read', async ({ world, as }) => {
  const pouch = await world.item('Belt Pouch');
  await world.slug(pouch, 'belt-pouch');
  await ok(
    world.gm.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { tenant_id: world.tenantId, entity_id: pouch } },
      body: {
        title: '',
        type: 'description',
        is_public: false,
        content: 'GM only: it hides a key.',
        locale: 'en',
      },
    }),
  );
  const backpack = await world.item('Backpack');
  await world.describe(backpack, 'See the [[Belt Pouch]].');

  // The GM reads it; the player gets the card without it.
  const gm = await as(world.gm);
  await gm.goto(`/item/?tenant=${world.tenantId}&id=${backpack}`);
  await link(gm).hover();
  await expect(card(gm)).toContainText('GM only: it hides a key.');

  const pia = await as(world.pia);
  await pia.goto(`/item/?tenant=${world.tenantId}&id=${backpack}`);
  await link(pia).hover();
  await expect(card(pia)).toContainText('Belt Pouch');
  await expect(card(pia)).not.toContainText('GM only');
});
