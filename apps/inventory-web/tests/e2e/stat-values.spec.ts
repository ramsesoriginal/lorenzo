import type { Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import type { World } from './support/world.ts';

async function gmOn(as: (who: World['gm']) => Promise<Page>, world: World, id: string) {
  const page = await as(world.gm);
  await page.goto(`/item/?tenant=${world.tenantId}&id=${id}`);
  return page;
}

/** What the API says an entity's stat is: its value and whether it is the entity's own. */
async function statOf(world: World, id: string, name: string) {
  const entity = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: world.tenantId, entity_id: id } },
    }),
  );
  return entity.stats.find((stat) => stat.name === name);
}

const statsRegion = (page: Page) => page.getByRole('region', { name: 'Stats' });

test('sets a stat on the item, and goes back to what it inherits', async ({ world, as }) => {
  const stick = await world.item('Stick', { stats: { weight: 2 } });
  const staff = await world.item('Staff', { prototypes: [stick] });
  const page = await gmOn(as, world, staff);
  const stats = statsRegion(page);
  const weight = stats.getByRole('form', { name: 'Weight stat' });

  await expect(weight.getByLabel('Weight', { exact: true })).toHaveValue('2');
  await expect(weight.locator('[data-source]')).toHaveText('Inherited');
  await expect(weight.getByRole('button', { name: 'Use inherited' })).toBeHidden();

  await weight.getByLabel('Weight', { exact: true }).fill('7');
  await weight.getByRole('button', { name: 'Save' }).click();
  await expect(stats.getByRole('status')).toHaveText('Saved.');
  await expect(weight.locator('[data-source]')).toHaveText('Set on this item');
  expect(await statOf(world, staff, 'weight')).toMatchObject({ value: 7, own: true });
  // What readers see changed with it.
  await expect(page.locator('[data-item-view]')).toContainText('7');

  await weight.getByRole('button', { name: 'Use inherited' }).click();
  await expect(weight.locator('[data-source]')).toHaveText('Inherited');
  await expect(weight.getByLabel('Weight', { exact: true })).toHaveValue('2');
  expect(await statOf(world, staff, 'weight')).toMatchObject({ value: 2, own: false });
});

test('chooses one of an enum stat’s values, and refuses a half as a whole number', async ({
  world,
  as,
}) => {
  const ring = await world.item('Ring');
  const page = await gmOn(as, world, ring);
  const stats = statsRegion(page);
  const binding = stats.getByRole('form', { name: 'Binding stat' });
  const weight = stats.getByRole('form', { name: 'Weight stat' });

  await expect(binding.locator('[data-source]')).toHaveText('Not set');
  await binding.getByLabel('Binding', { exact: true }).selectOption('on_equip');
  await binding.getByRole('button', { name: 'Save' }).click();
  await expect(binding.locator('[data-source]')).toHaveText('Set on this item');
  expect(await statOf(world, ring, 'binding')).toMatchObject({ value: 'on_equip', own: true });

  await weight.getByLabel('Weight', { exact: true }).fill('1.5');
  await weight.getByRole('button', { name: 'Save' }).click();
  await expect(stats.getByRole('status')).toHaveText('Weight: Enter a whole number.');
  expect(await statOf(world, ring, 'weight')).toBeUndefined();
});

test('says so when someone else changed the stat first, and shows theirs', async ({
  world,
  as,
}) => {
  const rope = await world.item('Rope', { stats: { weight: 1 } });
  const page = await gmOn(as, world, rope);
  const weight = statsRegion(page).getByRole('form', { name: 'Weight stat' });

  await expect(weight.getByLabel('Weight', { exact: true })).toHaveValue('1');
  await world.setStat(rope, 'weight', 5);
  await weight.getByLabel('Weight', { exact: true }).fill('9');
  await weight.getByRole('button', { name: 'Save' }).click();
  await expect(statsRegion(page).getByRole('status')).toContainText('Someone changed this stat');
  await expect(weight.getByLabel('Weight', { exact: true })).toHaveValue('5');
  expect(await statOf(world, rope, 'weight')).toMatchObject({ value: 5, own: true });
});

test('shows no stat controls to a player', async ({ world, as }) => {
  const lamp = await world.item('Lamp', { public: true });
  const pia = await as(world.pia);
  await pia.goto(`/item/?tenant=${world.tenantId}&id=${lamp}`);
  await expect(pia.getByRole('heading', { level: 1, name: 'Lamp' })).toBeVisible();
  await expect(statsRegion(pia)).toBeHidden();
});
