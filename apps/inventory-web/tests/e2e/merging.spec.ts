// Merging what's identical on a move (ADR 0133).
import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { Person, Player, World } from './support/world.ts';

async function boardOf(as: (who: Person) => Promise<Page>, world: World, player: Player) {
  const page = await as(player);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${player.character.entity_id}`);
  return page;
}

const column = (page: Page, name: string) => page.getByRole('region', { name });
const card = (page: Page, in_: string, name: string) =>
  column(page, in_).getByRole('button', { name, exact: true });

test('picks the pieces of a set-down stack up as one stack again', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);
  page.on('dialog', (dialog) => void dialog.accept());
  await card(page, 'Backpack', 'Arrow ×3').dragTo(column(page, 'Not carried'));
  await expect(card(page, 'Not carried', 'Arrow')).toHaveCount(3);

  await page.getByRole('button', { name: 'Select items' }).click();
  for (const arrow of await card(page, 'Not carried', 'Arrow').all()) await arrow.click();
  await expect(page.getByText('3 selected')).toBeVisible();
  await card(page, 'Not carried', 'Arrow').first().dragTo(column(page, 'Backpack'));

  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();
  await expect(card(page, 'Not carried', 'Arrow')).toHaveCount(0);
  await expect.poll(() => world.carried(world.pia)).toContain('Backpack: Arrow ×3');
});

test('moves an arrow onto a stack of them, which it joins, with no Undo', async ({ world, as }) => {
  const { items } = await packed(world, world.pia);
  await world.instance(items.arrow, { owner: world.pia, container: world.pia.character.entity_id });
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Equipped', 'Arrow').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Backpack', exact: true }).click();

  await expect(card(page, 'Backpack', 'Arrow ×4')).toBeVisible();
  await expect(card(page, 'Equipped', 'Arrow')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Undo' })).toBeHidden();
  expect(await world.carried(world.pia)).toContain('Backpack: Arrow ×4');
});
