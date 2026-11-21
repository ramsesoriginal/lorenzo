// A drag says where the card would land: the column is lit, a ghost sits in it with the words of what
// the move makes, a column that can't take it is outlined and refuses, and it all goes when the drag
// ends (IN12).
import type { Locator, Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { Person, World } from './support/world.ts';

async function boardOf(as: (who: Person) => Promise<Page>, world: World) {
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);
  return page;
}

const column = (page: Page, name: string) => page.getByRole('region', { name });
const card = (page: Page, in_: string, name: string) =>
  column(page, in_).getByRole('button', { name, exact: true });

/** Picks the card up and holds it over a column, without letting go. */
async function holdOver(page: Page, from: Locator, over: Locator) {
  const start = await from.boundingBox();
  const end = await over.boundingBox();

  if (!start || !end) throw new Error('Nothing to drag.');

  await page.mouse.move(start.x + 10, start.y + 10);
  await page.mouse.down();
  await page.mouse.move(start.x + 30, start.y + 30, { steps: 4 });
  await page.mouse.move(end.x + end.width / 2, end.y + 60, { steps: 8 });
}

test('lights the column and puts a ghost in it, saying what the move makes', async ({
  world,
  as,
}) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world);

  await holdOver(page, card(page, 'Backpack', 'Arrow ×3'), column(page, 'Belt Pouch'));

  await expect(column(page, 'Belt Pouch')).toHaveClass(/board-column--drop-target/);
  await expect(column(page, 'Belt Pouch').locator('.item-card--ghost')).toContainText('Arrow');
  // The card is dimmed where it was.
  await expect(page.locator('.item-card--dragging')).toHaveCount(1);

  await page.mouse.up();
  // Everything goes when the drag ends.
  await expect(page.locator('.item-card--ghost')).toHaveCount(0);
  await expect(page.locator('.item-card--dragging')).toHaveCount(0);
  await expect(card(page, 'Belt Pouch', 'Arrow ×3')).toBeVisible();
});

test("refuses a column that can't take it, in words, and doesn't drop", async ({ world, as }) => {
  const { backpack } = await packed(world, world.pia);
  await world.setStat(backpack, 'carry_capacity', 1);
  const anvil = await world.item('Anvil', { stats: { weight: 50 } });
  await world.instance(anvil, { owner: world.pia });
  const page = await boardOf(as, world);
  // What a container can carry arrives after the board is drawn.
  await expect(column(page, 'Backpack')).toContainText('of 1');

  await holdOver(page, card(page, 'Not carried', 'Anvil'), column(page, 'Backpack'));

  await expect(column(page, 'Backpack')).toHaveClass(/board-column--refuse/);
  await expect(column(page, 'Backpack').locator('.item-card--ghost')).toContainText('Too heavy');

  await page.mouse.up();
  await expect(page.locator('.item-card--ghost')).toHaveCount(0);
  await expect(card(page, 'Not carried', 'Anvil')).toBeVisible();
  expect(await world.ownedBy(world.pia.character.entity_id)).toContain('(none): Anvil');
});
