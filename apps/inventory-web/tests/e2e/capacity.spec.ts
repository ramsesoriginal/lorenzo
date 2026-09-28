// What a container can take, and a GM's "Move anyway" (ADR 0128).
import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { Person, World } from './support/world.ts';

async function piasBoard(as: (who: Person) => Promise<Page>, world: World, who: Person) {
  const page = await as(who);
  if (who === world.pia) {
    await page.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);
    return page;
  }
  // A GM browses to her character.
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('tab', { name: 'Browse a being' }).click();
  await page.getByLabel('Search beings').filter({ visible: true }).fill('Ashfang');
  await page.getByRole('option').getByRole('button', { name: 'Ashfang' }).click();
  return page;
}

const card = (page: Page, in_: string, name: string) =>
  page.getByRole('region', { name: in_ }).getByRole('button', { name, exact: true });

/**
 * Ashfang's Backpack can carry 1, and already holds a Spellbook (2); an Anvil (50) waits,
 * his but not carried.
 */
async function overloaded(world: World) {
  const { backpack } = await packed(world, world.pia);
  await world.setStat(backpack, 'carry_capacity', 1);
  const anvil = await world.item('Anvil', { stats: { weight: 50 } });
  await world.instance(anvil, { owner: world.pia });
}

async function moveAnvilIntoBackpack(page: Page) {
  await card(page, 'Not carried', 'Anvil').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Backpack', exact: true }).click();
}

test("a player sees why something doesn't fit", async ({ world, as }) => {
  await overloaded(world);
  const page = await piasBoard(as, world, world.pia);

  await moveAnvilIntoBackpack(page);

  await expect(page.getByText('Backpack can carry 1, and this would make it 52.')).toBeVisible();
  expect(await world.ownedBy(world.pia.character.entity_id)).toContain('(none): Anvil');
});

test('a GM moves it anyway, after being asked', async ({ world, as }) => {
  await overloaded(world);
  const page = await piasBoard(as, world, world.gm);
  let asked = '';
  page.once('dialog', (dialog) => {
    asked = dialog.message();
    void dialog.accept();
  });

  await moveAnvilIntoBackpack(page);

  await expect
    .poll(() => world.ownedBy(world.pia.character.entity_id))
    .toContain('Backpack: Anvil');
  expect(asked).toBe('Backpack can carry 1, and this would make it 52. Move anyway?');
});
