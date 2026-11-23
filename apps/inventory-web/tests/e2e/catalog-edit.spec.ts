// A game master writes a catalog item in place: the description saves as it is typed, and the link
// name, what it is made from and the public flag wait for the shell's save bar (IN5).
import type { Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import type { World } from './support/world.ts';

async function open(as: (who: World['gm']) => Promise<Page>, world: World, title: string) {
  const page = await as(world.gm);

  await page.goto(`/items/?tenant=${world.tenantId}`);
  await page
    .getByRole('list', { name: 'Catalog items' })
    .getByRole('button', { name: title })
    .click();

  return page;
}

const panel = (page: Page) => page.locator('[data-item-detail]');
const bar = (page: Page) => page.getByRole('region', { name: 'Unsaved changes' });

async function slugOf(world: World, id: string) {
  const entity = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: world.tenantId, entity_id: id } },
    }),
  );

  return entity.slug;
}

test('saves the description as it is typed', async ({ world, as }) => {
  const lantern = await world.item('Lantern');
  const page = await open(as, world, 'Lantern');

  await panel(page).getByLabel('Description saves as you type').fill('Burns oil for six hours.');
  await expect(panel(page).getByText('Saved')).toBeVisible();
  const info = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { tenant_id: world.tenantId, entity_id: lantern } },
    }),
  );

  expect(JSON.stringify(info)).toContain('Burns oil for six hours.');
});

test('keeps the link name behind the save bar, and refuses one that is taken', async ({
  world,
  as,
}) => {
  const taken = await world.item('Rope');
  await world.slug(taken, 'rope');
  const lantern = await world.item('Lantern');
  const page = await open(as, world, 'Lantern');

  await panel(page).getByLabel('Link name').fill('rope');
  await expect(bar(page)).toContainText('1 change not saved');
  await bar(page).getByRole('button', { name: 'Save changes' }).click();
  // It says why, the draft is kept, and nothing was written.
  await expect(page.getByText('Another entity already uses')).toBeVisible();
  await expect(panel(page).getByLabel('Link name')).toHaveValue('rope');
  expect(await slugOf(world, lantern)).not.toBe('rope');

  await panel(page).getByLabel('Link name').fill('hooded-lantern');
  await bar(page).getByRole('button', { name: 'Save changes' }).click();
  await expect.poll(() => slugOf(world, lantern)).toBe('hooded-lantern');
  await expect(page.locator('[data-shell-savebar][data-open]')).toHaveCount(0);
});

test('puts it in the public catalog with Save changes, and Discard puts it back', async ({
  world,
  as,
}) => {
  await world.item('Lantern');
  const page = await open(as, world, 'Lantern');

  await panel(page).getByLabel('In the public catalog').check();
  await expect(bar(page)).toBeVisible();
  await bar(page).getByRole('button', { name: 'Discard' }).click();
  await expect(panel(page).getByLabel('In the public catalog')).not.toBeChecked();
  await expect(page.locator('[data-shell-savebar][data-open]')).toHaveCount(0);

  await panel(page).getByLabel('In the public catalog').check();
  await bar(page).getByRole('button', { name: 'Save changes' }).click();
  await expect(
    page.getByRole('list', { name: 'Catalog items' }).getByText('Public', { exact: true }),
  ).toBeVisible();
});

test('refuses to leave with something not saved', async ({ world, as }) => {
  await world.item('Lantern');
  await world.item('Rope');
  const page = await open(as, world, 'Lantern');
  let asked = '';

  page.once('dialog', (dialog) => {
    asked = dialog.message();
    void dialog.dismiss();
  });
  await panel(page).getByLabel('Link name').fill('changed');
  await page
    .getByRole('list', { name: 'Catalog items' })
    .getByRole('button', { name: 'Rope' })
    .click();

  expect(asked).toContain('not saved');
  await expect(panel(page).getByRole('heading', { name: 'Lantern' })).toBeVisible();
});
