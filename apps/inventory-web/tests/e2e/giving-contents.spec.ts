// Giving a container with what's inside it, and giving everything inside (ADR 0125).
import type { Page } from '@playwright/test';
import { expect, readOnly, test } from './support/fixtures.ts';
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

async function pick(page: Page, search: string, name: string) {
  const box = page.getByLabel('Search beings').filter({ visible: true });
  await box.fill('');
  await box.fill(search);
  await page.getByRole('option').getByRole('button', { name }).click();
}

test("gives a backpack with what's inside it, asking first", async ({ world, as }) => {
  const { items, backpack } = await packed(world, world.pia);
  // Brisk's book, in Ashfang's backpack: it isn't hers to give, so it stays his.
  await world.instance(items.book, { owner: world.oskar, container: backpack });
  const company = await world.group('The Company', [world.pia, world.oskar]);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Equipped', 'Backpack').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await page.getByLabel("Also give what's inside").check();
  let asked = '';
  page.once('dialog', (dialog) => {
    asked = dialog.message();
    void dialog.accept();
  });
  await pick(page, 'Company', 'The Company (group)');

  await expect(
    page.getByText("Given to The Company, with 2 things inside. 1 thing inside stays Brisk's."),
  ).toBeVisible();
  expect(asked).toBe(
    "Give the Backpack and 2 things inside it to The Company? 1 thing inside stays Brisk's.",
  );
  // Nothing moves: the backpack stays in Ashfang's hands, the Company's now.
  await expect
    .poll(() => world.ownedBy(company))
    .toEqual(['Ashfang: Backpack', 'Backpack: Arrow', 'Backpack: Ornate Spellbook']);
  await expect
    .poll(() => world.ownedBy(world.oskar.character.entity_id))
    .toEqual(['Backpack: Book']);
  // Taking it back would only take the Backpack.
  await expect(page.getByRole('button', { name: 'Undo' })).toBeHidden();
});

test("gives what's inside a backpack, not the backpack", async ({ world, as }) => {
  const { items, backpack } = await packed(world, world.pia);
  await world.instance(items.book, { owner: world.oskar, container: backpack });
  const brisk = world.oskar.character.entity_id;
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Equipped', 'Backpack').click();
  await page.getByRole('button', { name: "Give what's inside…" }).click();

  // Asked, and said no: nothing changes.
  page.once('dialog', (dialog) => void dialog.dismiss());
  await pick(page, 'Brisk', 'Brisk');
  await expect(page.getByText('Nothing given.')).toBeVisible();
  expect(await world.ownedBy(brisk)).toEqual(['Backpack: Book']);

  page.once('dialog', (dialog) => void dialog.accept());
  await pick(page, 'Brisk', 'Brisk');
  await expect(page.getByText('Gave 2 things inside the Backpack to Brisk.')).toBeVisible();
  await expect
    .poll(() => world.ownedBy(brisk))
    .toEqual(['Backpack: Arrow', 'Backpack: Book', 'Backpack: Ornate Spellbook']);
  expect(await world.ownedBy(world.pia.character.entity_id)).toEqual([
    '(none): Backpack',
    '(none): Belt Pouch',
  ]);
});

readOnly(
  "offers what's inside only for a container with something in it",
  async ({ world, as }) => {
    const page = await boardOf(as, world, world.pia);

    await card(page, 'Equipped', 'Belt Pouch').click();
    await expect(page.getByRole('button', { name: "Give what's inside…" })).toBeHidden();
    await page.getByRole('button', { name: 'Give to…' }).click();
    await expect(page.getByLabel("Also give what's inside")).toHaveCount(0);
  },
);
