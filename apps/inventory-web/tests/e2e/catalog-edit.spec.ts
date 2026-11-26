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

test('shows only the tags it has, and adds one from the rest', async ({ world, as }) => {
  const blade = await world.item('Blade', { tags: ['is_magical'] });

  await world.item('Sword', { prototypes: [blade] });
  const page = await open(as, world, 'Sword');
  const tags = panel(page).locator('.item-editor-tags');

  // What it has from the blade is shown as that; what it has not is not there to look as if it had.
  await expect(tags.getByRole('listitem').filter({ hasText: 'Magical' })).toContainText(
    'from Blade',
  );
  await expect(tags.getByRole('listitem').filter({ hasText: 'Cursed' })).toHaveCount(0);
  await expect(tags.getByRole('listitem')).toHaveCount(1);

  await panel(page).getByLabel('Add a tag').selectOption({ label: 'Cursed' });
  await expect(tags.getByRole('listitem').filter({ hasText: 'Cursed' })).toBeVisible();
  await expect(
    panel(page).getByLabel('Add a tag').getByRole('option', { name: 'Cursed' }),
  ).toHaveCount(0);

  // Taking away what is its own; what it inherits is turned off here, and stays on the blade.
  await panel(page).getByRole('button', { name: 'Remove Cursed' }).click();
  await expect(tags.getByRole('listitem').filter({ hasText: 'Cursed' })).toHaveCount(0);
  await panel(page).getByRole('button', { name: 'Remove Magical' }).click();
  await expect(tags.getByRole('listitem')).toHaveCount(0);
});

test('shows the stats it inherits, and a value typed over one is its own', async ({
  world,
  as,
}) => {
  const blade = await world.item('Blade', { stats: { weight: 3, price: 40 } });
  const sword = await world.item('Sword', { prototypes: [blade] });
  const page = await open(as, world, 'Sword');
  const weight = panel(page).getByLabel(/^Weight/);

  await expect(weight).toHaveValue('3');
  await expect(panel(page).getByLabel(/^Price/)).toHaveValue('40');
  await expect(panel(page).getByText('Inherited from Blade').first()).toBeVisible();

  await weight.fill('5');
  await weight.blur();
  await expect(panel(page).getByText('Set on this item')).toBeVisible();

  const stats = async (id: string) =>
    (
      await ok(
        world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
          params: { path: { tenant_id: world.tenantId, entity_id: id } },
        }),
      )
    ).stats.find((stat) => stat.name === 'weight');

  expect((await stats(sword))?.value).toBe(5);
  expect((await stats(sword))?.own).toBe(true);
  // The blade keeps its own.
  expect((await stats(blade))?.value).toBe(3);

  // Clearing it gives it back what it inherits.
  await panel(page).getByRole('button', { name: 'Clear Weight' }).click();
  await expect(weight).toHaveValue('3');
});

test('adds a stat it does not have yet', async ({ world, as }) => {
  const sword = await world.item('Sword');
  const page = await open(as, world, 'Sword');

  await expect(panel(page).getByLabel(/^Price/)).toHaveCount(0);
  await panel(page).getByLabel('Add a stat').selectOption({ label: 'Price' });
  await panel(page)
    .getByLabel(/^Price/)
    .fill('12');
  await panel(page)
    .getByLabel(/^Price/)
    .blur();
  await expect(panel(page).getByText('Set on this item')).toBeVisible();

  const entity = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: world.tenantId, entity_id: sword } },
    }),
  );

  expect(entity.stats.find((stat) => stat.name === 'price')?.value).toBe(12);
});

test('reads what its ancestors say beside what it says', async ({ world, as }) => {
  const blade = await world.item('Blade', { description: 'Keen on both edges.' });

  await world.item('Sword', { prototypes: [blade] });
  await world.item('Plain');
  const page = await open(as, world, 'Sword');

  await expect(
    panel(page).getByRole('heading', { name: /Inherited from what it is made from/ }),
  ).toBeVisible();
  await expect(panel(page).getByText('Keen on both edges.')).toBeVisible();
  await expect(panel(page).getByRole('link', { name: 'Blade' }).first()).toBeVisible();
  // It is not its own text: the field it writes in stays empty.
  await expect(panel(page).getByLabel('Description saves as you type')).not.toHaveValue(
    /Keen on both edges/,
  );

  // With nothing inherited there is nothing to head.
  await page
    .getByRole('list', { name: 'Catalog items' })
    .getByRole('button', { name: 'Plain' })
    .click();
  await expect(panel(page).getByRole('heading', { name: 'Plain' })).toBeVisible();
  await expect(
    panel(page).getByRole('heading', { name: /Inherited from what it is made from/ }),
  ).toBeHidden();
});
