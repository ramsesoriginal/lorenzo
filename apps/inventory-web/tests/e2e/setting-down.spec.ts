// Setting things down, out of every container, and a stack as single items (ADR 0132).
import type { Locator, Page } from '@playwright/test';
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

/** The row of a list whose own title is exactly `name`. */
const row = (list: Locator, name: string) =>
  list.getByRole('listitem').filter({ has: list.page().getByText(name, { exact: true }) });

test('sets a thing down from its dialog, and undoes it', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('button', { name: 'Set down' }).click();

  await expect(card(page, 'Not carried', 'Ornate Spellbook')).toBeVisible();
  await expect(page.getByText('Set down Ornate Spellbook.')).toBeVisible();
  // Still hers, but in no container at all.
  expect(await world.ownedBy(world.pia.character.entity_id)).toContain('(none): Ornate Spellbook');

  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
});

test('drops a stack on Not carried as single items, after asking', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  // Asked, and told no: it stays a stack in the backpack.
  page.once('dialog', (dialog) => void dialog.dismiss());
  await card(page, 'Backpack', 'Arrow ×3').dragTo(column(page, 'Not carried'));
  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();

  let asked = '';
  page.once('dialog', (dialog) => {
    asked = dialog.message();
    void dialog.accept();
  });
  await card(page, 'Backpack', 'Arrow ×3').dragTo(column(page, 'Not carried'));

  await expect(card(page, 'Not carried', 'Arrow')).toHaveCount(3);
  expect(asked).toBe('Setting down Arrow ×3 leaves 3 separate items. Set it down?');
  await expect(page.getByRole('button', { name: 'Undo' })).toBeHidden();
  const arrows = (await world.carried(world.pia)).filter((line) => line.endsWith('Arrow'));
  expect(arrows).toEqual(['(none): Arrow', '(none): Arrow', '(none): Arrow']);
});

test("a GM deletes a chest that's lying somewhere, setting down what was in it", async ({
  world,
  as,
}) => {
  const { items } = await packed(world, world.pia);
  const chestItem = await world.item('Chest', { tags: ['is_container'] });
  const chest = await world.instance(chestItem, { owner: world.pia });
  await world.stack(items.arrow, 2, { owner: world.pia, container: chest });
  const page = await as(world.gm);
  await page.goto(`/items/?tenant=${world.tenantId}`);
  const instances = page.getByRole('region', { name: 'Instances' });
  await page.getByRole('combobox', { name: "View a being's inventory" }).fill('Ashf');
  await instances.getByRole('option').getByRole('button', { name: 'Ashfang' }).click();

  const asked: string[] = [];
  page.on('dialog', (dialog) => {
    asked.push(dialog.message());
    void dialog.accept();
  });
  await row(instances, 'Chest').getByRole('button', { name: 'Delete' }).click();

  await expect(row(instances, 'Chest')).toBeHidden();
  expect(asked[1]).toBe(
    `Deleting "Chest" sets down what's inside it, and a stack among that becomes single items. Delete it?`,
  );
  // Out of every container, not into her hands.
  const arrows = (await world.carried(world.pia)).filter((line) => line.endsWith('Arrow'));
  expect(arrows).toEqual(['(none): Arrow', '(none): Arrow']);
});
