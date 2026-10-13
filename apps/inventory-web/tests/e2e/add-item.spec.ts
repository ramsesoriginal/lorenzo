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

// --- "Not in the list" and the unsorted badge (ADR 0238) --------------------------------------

/** The library's placeholder, as `lorenzo seed --layer core` makes it (ADR 0192). */
async function seedUnsorted(world: World): Promise<string> {
  const id = await world.item('Unsorted item', { public: true });
  await world.slug(id, 'unsorted');
  return id;
}

const notListed = (page: Page) =>
  card(page).getByRole('button', { name: 'Not in the list? Add it as an unsorted item' });

/** The notes on `title`, as its owner reads them: title to text. */
async function notesOn(world: World, player: Player, title: string) {
  const path = { tenant_id: world.tenantId };
  const owned = await ok(
    player.api.GET('/tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}', {
      params: { path: { ...path, owner_entity_id: player.character.entity_id } },
    }),
  );
  const made = owned.groups.flatMap((g) => g.item_instances).find((i) => i.title === title);
  if (!made) throw new Error(`${title} is not owned`);
  const notes = await ok(
    player.api.GET('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { ...path, entity_id: made.entity_id }, query: { type: ['note'] } },
    }),
  );
  return Object.fromEntries(
    notes.items.map((note) => {
      const text = note.payloads.find((p) => 'content' in p);
      return [note.title, text && 'content' in text ? text.content : ''];
    }),
  );
}

test('a player adds what the catalog does not know as an unsorted item, with notes', async ({
  world,
  as,
}) => {
  await seedUnsorted(world);
  await world.item('Rope', { public: true });
  const page = await boardOf(as, world, world.pia);

  // Typed in the search, and nothing matches.
  await search(page).fill('Hydra Zahn');
  await expect(card(page).getByText('No item matches “Hydra Zahn”.')).toBeVisible();
  await notListed(page).click();

  // The name is what was typed.
  await expect(card(page).getByLabel('Name')).toHaveValue('Hydra Zahn');
  await card(page).getByLabel('Description (optional)').fill('from the cave under the temple');
  await card(page).getByLabel('Weight in pounds (optional)').fill('0,5');
  await card(page).getByLabel('Value (optional)').fill('?');
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();

  await expect(
    card(page).getByText("Added Hydra Zahn to Ashfang's Not carried as an unsorted item."),
  ).toBeVisible();
  const added = column(page, 'Not carried').getByRole('button', { name: /Hydra Zahn/ });
  await expect(added).toBeVisible();
  await expect(added.getByText('Unsorted')).toBeVisible();
  expect(await world.carried(world.pia)).toEqual(['(none): Hydra Zahn']);
  // The player can read back what they wrote, laid out as the CLI writes it (ADR 0193).
  expect(await notesOn(world, world.pia, 'Hydra Zahn')).toEqual({
    Note: 'from the cave under the temple',
    Details: 'Weight: 0.5 lb\nValue: ?',
  });
});

test('takes an unsorted item back with Undo', async ({ world, as }) => {
  await seedUnsorted(world);
  const page = await boardOf(as, world, world.pia);

  await notListed(page).click();
  await card(page).getByLabel('Name').fill('Fishing rod');
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();
  await expect(card(page).getByText(/^Added Fishing rod/)).toBeVisible();

  await card(page).getByRole('button', { name: 'Undo' }).click();

  await expect(card(page).getByText('Taken back.')).toBeVisible();
  expect(await world.carried(world.pia)).toEqual([]);
});

test('asks for a name, and for a weight that is a number, and makes nothing otherwise', async ({
  world,
  as,
}) => {
  await seedUnsorted(world);
  const page = await boardOf(as, world, world.pia);

  await notListed(page).click();
  await card(page).getByLabel('Name').fill('   ');
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();
  await expect(card(page).getByText('Give it a name.')).toBeVisible();

  await card(page).getByLabel('Name').fill('Anvil');
  await card(page).getByLabel('Weight in pounds (optional)').fill('heavy');
  await card(page).getByRole('button', { name: 'Add to Ashfang' }).click();
  await expect(card(page).getByText('Weight is a number of pounds, such as 0.5.')).toBeVisible();
  expect(await world.carried(world.pia)).toEqual([]);

  // Back to the catalog search, with the option still there.
  await card(page).getByRole('button', { name: 'Back' }).click();
  await expect(search(page)).toBeVisible();
  await expect(notListed(page)).toBeVisible();
});

test('says what the GM runs when the library has no unsorted item', async ({ world, as }) => {
  await world.item('Rope', { public: true });
  const page = await boardOf(as, world, world.pia);

  await expect(card(page).getByText(/can't take unsorted items yet/)).toBeVisible();
  await expect(card(page).getByText('lorenzo seed --layer core')).toBeVisible();
  await expect(notListed(page)).toBeHidden();
});

test('marks only the unsorted things on the board', async ({ world, as }) => {
  const unsorted = await seedUnsorted(world);
  const rope = await world.item('Rope', { public: true });
  await world.instance(unsorted, { owner: world.pia });
  await world.instance(rope, { owner: world.pia });
  const page = await boardOf(as, world, world.pia);

  const notCarried = column(page, 'Not carried');
  await expect(notCarried.getByRole('button', { name: /Unsorted item/ })).toBeVisible();
  // Every card carries the badge, hidden unless it is one: count the ones that show.
  await expect(notCarried.locator('[data-unsorted]:not([hidden])')).toHaveCount(1);
  await expect(
    notCarried.getByRole('button', { name: /^Rope/ }).getByText('Unsorted'),
  ).toBeHidden();
});
