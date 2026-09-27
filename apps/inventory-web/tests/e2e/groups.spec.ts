// Groups own things, and moving something isn't giving it away (ADR 0124).
import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { catalog, packed } from './support/scenes.ts';
import type { Person, Player, World } from './support/world.ts';

async function boardOf(as: (who: Person) => Promise<Page>, world: World, player: Player) {
  const page = await as(player);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${player.character.entity_id}`);
  return page;
}

const column = (page: Page, name: string) => page.getByRole('region', { name });
const card = (page: Page, in_: string, name: string) =>
  column(page, in_).getByRole('button', { name, exact: true });

test("a member opens the group's board from the strip", async ({ world, as }) => {
  const items = await catalog(world);
  const company = await world.group('The Company', [world.pia, world.oskar]);
  const chest = await world.instance(items.backpack, { ownerId: company });
  await world.instance(items.arrow, { ownerId: company, container: chest });

  const page = await boardOf(as, world, world.pia);
  await page
    .getByRole('list', { name: 'Your groups' })
    .getByRole('button', { name: 'The Company' })
    .click();

  await expect(page.getByText('Viewing what The Company holds.')).toBeVisible();
  await expect(card(page, 'The Company', 'Backpack')).toBeVisible();
  await expect(card(page, 'Backpack', 'Arrow')).toBeVisible();
  await expect(page).toHaveURL(`/board/?tenant=${world.tenantId}&group=${company}`);
});

test('gives something to a group', async ({ world, as }) => {
  await packed(world, world.pia);
  const company = await world.group('The Company', [world.pia, world.oskar]);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await page.getByLabel('Search beings').filter({ visible: true }).fill('Company');
  await page.getByRole('option').getByRole('button', { name: 'The Company (group)' }).click();

  await expect(page.getByText('Given to The Company.')).toBeVisible();
  await expect.poll(() => world.ownedBy(company)).toEqual(['Backpack: Ornate Spellbook']);

  // Her own group: she may give it back, so she keeps her Undo.
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect.poll(() => world.ownedBy(company)).toEqual([]);
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
});

test("carrying someone else's thing lets you move it, not give it away", async ({ world, as }) => {
  const { items, backpack } = await packed(world, world.pia);
  // Brisk's book, in Ashfang's backpack.
  await world.instance(items.book, { owner: world.oskar, container: backpack });
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', "Book Brisk's").click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await page.getByLabel('Search beings').filter({ visible: true }).fill('Ashfang');
  await page.getByRole('option').getByRole('button', { name: 'Ashfang' }).click();
  await expect(page.getByText('only its owner or a GM can give it away')).toBeVisible();
  await page.keyboard.press('Escape');

  // Moving it is hers to do.
  await card(page, 'Backpack', "Book Brisk's").dragTo(column(page, 'Equipped'));
  await expect(card(page, 'Equipped', "Book Brisk's")).toBeVisible();
  await expect
    .poll(() => world.ownedBy(world.oskar.character.entity_id))
    .toEqual(['Ashfang: Book']);
});
