// Unpacking a pack from its dialog on the board (ADR 0189).
import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import type { Person, Player, World } from './support/world.ts';

const LIST =
  'This pack contains:\n\n- 1 x [Backpack](unpack-backpack)\n  - 5 x [Rations](unpack-rations)\n- 2 x [Rope](unpack-rope)';

/** An "Explorer's pack" whose list names public items, and a pack instance of it for Pia. */
async function packFor(world: World, player: Player, { publicItems = true } = {}) {
  const backpack = await world.item('Backpack', { public: publicItems });
  const rations = await world.item('Rations', { public: publicItems });
  const rope = await world.item('Rope', { public: true });
  await world.slug(backpack, 'unpack-backpack');
  await world.slug(rations, 'unpack-rations');
  await world.slug(rope, 'unpack-rope');
  const pack = await world.item("Explorer's pack", { public: true, description: LIST });
  return { pack, instance: await world.instance(pack, { owner: player }) };
}

async function boardOf(as: (who: Person) => Promise<Page>, world: World, player: Player) {
  const page = await as(player);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${player.character.entity_id}`);
  return page;
}

const card = (page: Page, name: string) =>
  page.getByRole('region', { name: 'Not carried' }).getByRole('button', { name, exact: true });
const dialog = (page: Page) => page.getByRole('dialog');

test("a GM unpacks a player's pack: what it lists, then the pack gone", async ({ world, as }) => {
  await packFor(world, world.pia);
  const page = await as(world.gm);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('tab', { name: 'Browse a being' }).click();
  await page.getByLabel('Search beings').filter({ visible: true }).fill('Ashfang');
  await page.getByRole('option').getByRole('button', { name: 'Ashfang' }).click();

  await card(page, "Explorer's pack").click();
  await dialog(page).getByRole('button', { name: 'Unpack…' }).click();
  await expect(
    dialog(page).getByText(
      "Unpacking Explorer's pack makes Backpack (Rations ×5), Rope ×2, and the pack goes. This can't be undone.",
    ),
  ).toBeVisible();
  // Asking made nothing.
  expect(await world.carried(world.pia)).toEqual(["(none): Explorer's pack"]);

  await dialog(page).getByRole('button', { name: 'Unpack', exact: true }).click();
  await expect(dialog(page)).toBeHidden();

  expect(await world.carried(world.pia)).toEqual([
    '(none): Backpack',
    '(none): Rope ×2',
    'Backpack: Rations ×5',
  ]);
});

test('a player unpacks their own pack when everything in it is public', async ({ world, as }) => {
  await packFor(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, "Explorer's pack").click();
  await dialog(page).getByRole('button', { name: 'Unpack…' }).click();
  await dialog(page).getByRole('button', { name: 'Unpack', exact: true }).click();
  await expect(dialog(page)).toBeHidden();

  await expect(
    page.getByRole('region', { name: 'Equipped' }).getByRole('button', { name: 'Backpack' }),
  ).toBeVisible();
  await expect(card(page, "Explorer's pack")).toBeHidden();
});

test("a player isn't let to unpack a pack with something private in it, and nothing changes", async ({
  world,
  as,
}) => {
  await packFor(world, world.pia, { publicItems: false });
  const page = await boardOf(as, world, world.pia);

  await card(page, "Explorer's pack").click();
  await dialog(page).getByRole('button', { name: 'Unpack…' }).click();

  await expect(dialog(page).getByText(/can't be handed out as it is/)).toBeVisible();
  await expect(dialog(page).getByRole('button', { name: 'Unpack', exact: true })).toBeHidden();
  expect(await world.carried(world.pia)).toEqual(["(none): Explorer's pack"]);
});

test('offers nothing on an item that does not list contents', async ({ world, as }) => {
  const rope = await world.item('Rope', { public: true });
  await world.instance(rope, { owner: world.pia });
  const { pack } = await packFor(world, world.pia);
  await world.instance(pack, { owner: world.pia });
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Rope').click();
  await expect(dialog(page).getByRole('button', { name: 'Give to…' })).toBeVisible();
  await expect(dialog(page).getByRole('button', { name: 'Unpack…' })).toBeHidden();
});

test('a stack of packs is unpacked one at a time: the button says to split one off', async ({
  world,
  as,
}) => {
  const { pack } = await packFor(world, world.pia);
  await world.stack(pack, 2, { owner: world.pia, container: world.pia.character.entity_id });
  const page = await boardOf(as, world, world.pia);

  await page
    .getByRole('region', { name: 'Equipped' })
    .getByRole('button', { name: /Explorer's pack/ })
    .click();

  const unpack = dialog(page).getByRole('button', { name: 'Unpack…' });
  await expect(unpack).toBeDisabled();
  await expect(unpack).toHaveAttribute('title', 'Split one off to unpack it.');
});
