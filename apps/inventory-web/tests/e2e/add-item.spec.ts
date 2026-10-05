// Adding an item from the board (ADR 0187): a player makes their own, from the public catalog.
import type { Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import type { Person, Player, World } from './support/world.ts';

async function boardOf(as: (who: Person) => Promise<Page>, world: World, player: Player) {
  const page = await as(player);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${player.character.entity_id}`);
  return page;
}

const card = (page: Page) => page.getByRole('region', { name: 'Add an item' });
const column = (page: Page, name: string) => page.getByRole('region', { name });
const search = (page: Page) => card(page).getByRole('combobox', { name: 'Find an item' });

/** Picks `name` from the catalog suggestions. */
async function pick(page: Page, name: string) {
  await search(page).click();
  await card(page).getByRole('option').getByRole('button', { name, exact: true }).click();
}

async function setCampaign(world: World, player_self_service: boolean) {
  await ok(
    world.gm.api.PATCH('/tenants/{tenant_id}/campaigns/{campaign_id}', {
      params: { path: { tenant_id: world.tenantId, campaign_id: world.campaignId } },
      body: { player_self_service },
    }),
  );
}

test('a player finds an item in the public catalog and adds it, not carried', async ({
  world,
  as,
}) => {
  await world.item('Shortsword', { public: true });
  await world.item('Vault key');
  const page = await boardOf(as, world, world.pia);

  await expect(card(page)).toBeVisible();
  // Focusing offers what's there, with no name to type; what the GM kept back isn't.
  await search(page).click();
  await expect(card(page).getByRole('option')).toHaveText(['Shortsword']);

  await card(page).getByRole('option').getByRole('button', { name: 'Shortsword' }).click();
  // Picking only chooses: nothing is made until it's confirmed.
  expect(await world.carried(world.pia)).toEqual([]);
  await expect(card(page).getByText('Shortsword', { exact: true })).toBeVisible();
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();

  await expect(card(page).getByText("Added Shortsword to Ashfang's Not carried.")).toBeVisible();
  await expect(
    column(page, 'Not carried').getByRole('button', { name: 'Shortsword', exact: true }),
  ).toBeVisible();
  expect(await world.carried(world.pia)).toEqual(['(none): Shortsword']);
});

test('lets her name it', async ({ world, as }) => {
  await world.item('Shortsword', { public: true });
  const page = await boardOf(as, world, world.pia);

  await pick(page, 'Shortsword');
  await card(page).getByLabel('Call it (optional)').fill("Aldric's blade");
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();

  await expect(
    column(page, 'Not carried').getByRole('button', { name: "Aldric's blade" }),
  ).toBeVisible();
  expect(await world.carried(world.pia)).toEqual(["(none): Aldric's blade"]);
});

test('takes it back with Undo', async ({ world, as }) => {
  await world.item('Shortsword', { public: true });
  const page = await boardOf(as, world, world.pia);

  await pick(page, 'Shortsword');
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();
  await expect(card(page).getByText("Added Shortsword to Ashfang's Not carried.")).toBeVisible();

  await card(page).getByRole('button', { name: 'Undo' }).click();

  await expect(card(page).getByText('Taken back.')).toBeVisible();
  await expect(card(page).getByRole('button', { name: 'Undo' })).toBeHidden();
  await expect(
    column(page, 'Not carried').getByRole('button', { name: 'Shortsword' }),
  ).toBeHidden();
  expect(await world.carried(world.pia)).toEqual([]);
});

test('can pick another before adding, and searches by name', async ({ world, as }) => {
  await world.item('Shortsword', { public: true });
  await world.item('Rope', { public: true });
  const page = await boardOf(as, world, world.pia);

  await pick(page, 'Shortsword');
  await card(page).getByRole('button', { name: 'Pick another' }).click();
  await search(page).fill('rop');
  await card(page).getByRole('option').getByRole('button', { name: 'Rope' }).click();
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();

  await expect(column(page, 'Not carried').getByRole('button', { name: 'Rope' })).toBeVisible();
  expect(await world.carried(world.pia)).toEqual(['(none): Rope']);
});

test('says when nothing matches, and when the catalog is empty', async ({ world, as }) => {
  const page = await boardOf(as, world, world.pia);

  await search(page).click();
  await expect(card(page).getByText('Nothing is in the catalog yet.')).toBeVisible();

  await world.item('Rope', { public: true });
  await search(page).fill('zzz');
  await expect(card(page).getByText('No item matches “zzz”.')).toBeVisible();
});

test('says it is switched off, and offers nothing, when the GM has switched it off', async ({
  world,
  as,
}) => {
  await world.item('Shortsword', { public: true });
  await setCampaign(world, false);
  const page = await boardOf(as, world, world.pia);

  await expect(
    card(page).getByText('Your GM has switched off adding items for Ashfang.'),
  ).toBeVisible();
  await expect(search(page)).toBeHidden();
});

test('a GM can still switch it on for one player, whatever the campaign says', async ({
  world,
  as,
}) => {
  await world.item('Shortsword', { public: true });
  await setCampaign(world, false);
  await ok(
    world.gm.api.PATCH('/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}', {
      params: {
        path: {
          tenant_id: world.tenantId,
          campaign_id: world.campaignId,
          player_id: world.pia.playerId,
        },
      },
      body: { self_service: true },
    }),
  );
  const page = await boardOf(as, world, world.pia);

  await pick(page, 'Shortsword');
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();

  await expect(
    column(page, 'Not carried').getByRole('button', { name: 'Shortsword' }),
  ).toBeVisible();
});

test("a group's board offers nothing to add", async ({ world, as }) => {
  await world.item('Shortsword', { public: true });
  const company = await world.group('The Company', [world.pia, world.oskar]);
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}&group=${company}`);

  await expect(column(page, 'Not carried')).toBeVisible();
  await expect(card(page)).toBeHidden();
});

test('a GM adds to any being, and sees the whole catalog, not only the public one', async ({
  world,
  as,
}) => {
  await world.item('Vault key');
  const page = await as(world.gm);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('tab', { name: 'Browse a being' }).click();
  await page.getByLabel('Search beings').filter({ visible: true }).fill('Brisk');
  await page.getByRole('option').getByRole('button', { name: 'Brisk' }).click();

  await pick(page, 'Vault key');
  await card(page).getByRole('button', { name: 'Add to Brisk' }).click();

  await expect(
    column(page, 'Not carried').getByRole('button', { name: 'Vault key' }),
  ).toBeVisible();
  expect(await world.carried(world.oskar)).toEqual(['(none): Vault key']);
});
