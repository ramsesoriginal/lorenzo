// The GM's Unsorted view (ADR 0241): placeholders by the name written, given to a catalog item,
// made into a new one, or kept.
import type { Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import { buildWorld, type Player, type World } from './support/world.ts';

/** The library's placeholder, as `lorenzo seed --layer core` makes it (ADR 0192). */
async function seedUnsorted(world: World): Promise<string> {
  const id = await world.item('Unsorted item', { public: true });
  await world.slug(id, 'unsorted');
  return id;
}

/** What a player's import or "Not in the list" leaves: the placeholder, under the player's name. */
async function unsortedFor(world: World, unsortedId: string, player: Player, name: string) {
  const made = await ok(
    player.api.POST('/tenants/{tenant_id}/item-instances', {
      params: { path: { tenant_id: world.tenantId } },
      body: {
        prototype_id: unsortedId,
        owner_character_id: player.character.entity_id,
        name,
        override: false,
        quantity: 1,
      },
    }),
  );

  return made.entity_id;
}

async function noteOn(world: World, player: Player, entityId: string, text: string) {
  const note = await ok(
    player.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { tenant_id: world.tenantId, entity_id: entityId } },
      body: { title: 'Note', type: 'note', is_public: false, content: text, locale: 'en' },
    }),
  );
  // The author tells their own character, as the clients do (ADR 0192).
  await ok(
    player.api.PUT('/tenants/{tenant_id}/information/{information_id}/knowers/{knower_entity_id}', {
      params: {
        path: {
          tenant_id: world.tenantId,
          information_id: note.id,
          knower_entity_id: player.character.entity_id,
        },
      },
    }),
  );
}

/** The names of the instances whose direct prototype is `prototypeId`, as the GM sees them. */
async function made(world: World, prototypeId: string): Promise<string[]> {
  const page = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/item-instances', {
      params: { path: { tenant_id: world.tenantId }, query: { prototype_id: prototypeId } },
    }),
  );

  return page.items.map((i) => i.title).sort();
}

const group = (page: Page, name: string) =>
  page
    .getByRole('listitem')
    .filter({ has: page.getByText(name, { exact: true }) })
    .first();

async function unsortedPage(as: (w: World['gm']) => Promise<Page>, world: World) {
  const page = await as(world.gm);

  await page.goto(`/unsorted/?tenant=${world.tenantId}`);

  return page;
}

test('groups what players wrote by name, however they spelled it', async ({ world, as }) => {
  const unsorted = await seedUnsorted(world);
  await unsortedFor(world, unsorted, world.pia, 'Torch');
  await unsortedFor(world, unsorted, world.oskar, 'torch.');
  await unsortedFor(world, unsorted, world.oskar, 'Hydra Zahn');
  const page = await unsortedPage(as, world);

  await expect(group(page, 'Torch')).toContainText('2 items');
  await expect(group(page, 'Hydra Zahn')).toContainText('1 item');
});

test('gives a whole group to the catalog item it looks like, names and holders kept', async ({
  world,
  as,
}) => {
  const unsorted = await seedUnsorted(world);
  const torch = await world.item('Torch', { public: true });
  await world.item('Anvil');
  await unsortedFor(world, unsorted, world.pia, 'Torches');
  await unsortedFor(world, unsorted, world.oskar, 'torches');
  const page = await unsortedPage(as, world);

  await group(page, 'Torches').getByRole('button', { name: 'Sort' }).click();
  // Suggested by how alike the names are; the Anvil is not.
  await expect(
    group(page, 'Torches').getByRole('button', { name: 'Torch', exact: true }),
  ).toBeVisible();
  await expect(group(page, 'Torches').getByRole('button', { name: 'Anvil' })).toHaveCount(0);
  await group(page, 'Torches').getByRole('button', { name: 'Torch', exact: true }).click();
  await group(page, 'Torches').getByRole('button', { name: 'Assign 2 to Torch' }).click();

  await expect(page.getByText('2 items sorted as Torch.')).toBeVisible();
  await expect(page.getByText('Nothing is unsorted.')).toBeVisible();
  expect(await made(world, unsorted)).toEqual([]);
  // The players' own names stay on what they hold.
  expect(await made(world, torch)).toEqual(['Torches', 'torches']);
  expect(await world.carried(world.pia)).toEqual(['(none): Torches']);
});

test('suggests the catalog item a German name stands for, from the table of spellings', async ({
  world,
  as,
}) => {
  const unsorted = await seedUnsorted(world);
  await world.item('Rope, hempen (50 feet)', { public: true });
  await world.item('Rope, silk (50 feet)', { public: true });
  await unsortedFor(world, unsorted, world.pia, 'Seil');
  const page = await unsortedPage(as, world);

  await group(page, 'Seil').getByRole('button', { name: 'Sort' }).click();

  // The letters of "Seil" are in neither title; the table says which rope it is (ADR 0242).
  const looksLike = group(page, 'Seil').getByRole('button', { name: /^Rope/ });
  // The one the table names comes first; the other rope is only a near miss.
  await expect(looksLike.first()).toHaveText('Rope, hempen (50 feet)');
});

test('sorts only the ones that are ticked', async ({ world, as }) => {
  const unsorted = await seedUnsorted(world);
  const rope = await world.item('Rope', { public: true });
  await unsortedFor(world, unsorted, world.pia, 'Rope');
  await unsortedFor(world, unsorted, world.oskar, 'Rope');
  const page = await unsortedPage(as, world);

  await group(page, 'Rope').getByRole('button', { name: 'Sort' }).click();
  await group(page, 'Rope').getByRole('checkbox', { name: 'Brisk' }).uncheck();
  await group(page, 'Rope').getByRole('button', { name: 'Rope', exact: true }).first().click();
  await group(page, 'Rope').getByRole('button', { name: 'Assign 1 to Rope' }).click();

  await expect(page.getByText('1 item sorted as Rope.')).toBeVisible();
  expect(await made(world, rope)).toEqual(['Rope']);
  expect(await made(world, unsorted)).toEqual(['Rope']);
});

test('makes a catalog item of a group, its description from the player note', async ({
  world,
  as,
}) => {
  const unsorted = await seedUnsorted(world);
  const zahn = await unsortedFor(world, unsorted, world.pia, 'Hydra Zahn');
  await noteOn(world, world.pia, zahn, 'from the cave under the temple');
  const page = await unsortedPage(as, world);

  await group(page, 'Hydra Zahn').getByRole('button', { name: 'Sort' }).click();
  await expect(page.getByText('Note: from the cave under the temple')).toBeVisible();
  await group(page, 'Hydra Zahn').getByLabel('Name of the new item').fill('Hydra Tooth');
  await group(page, 'Hydra Zahn').getByRole('button', { name: 'Create and assign' }).click();

  await expect(page.getByText('1 item sorted as Hydra Tooth.')).toBeVisible();
  const items = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/items', {
      params: { path: { tenant_id: world.tenantId }, query: { q: 'Hydra Tooth' } },
    }),
  );
  const [tooth] = items.items;
  expect(tooth?.title).toBe('Hydra Tooth');
  expect(await made(world, tooth?.entity_id as string)).toEqual(['Hydra Zahn']);
  expect(tooth?.descriptions[0]?.content).toBe('from the cave under the temple');
});

test('keeps a group as it is, until the page is loaded again', async ({ world, as }) => {
  const unsorted = await seedUnsorted(world);
  await unsortedFor(world, unsorted, world.pia, 'Mystery');
  const page = await unsortedPage(as, world);

  await group(page, 'Mystery').getByRole('button', { name: 'Sort' }).click();
  await group(page, 'Mystery').getByRole('button', { name: 'Keep as it is' }).click();
  await expect(group(page, 'Mystery')).toHaveCount(0);
  expect(await made(world, unsorted)).toEqual(['Mystery']);

  await page.reload();
  await expect(group(page, 'Mystery')).toBeVisible();
});

test('is a GM page, and says what to run when the library has no unsorted item', async ({
  world,
  as,
}) => {
  const player = await as(world.pia);
  await seedUnsorted(world);
  await player.goto(`/unsorted/?tenant=${world.tenantId}`);
  await expect(player.getByText('Sorting unsorted items is for a GM.')).toBeVisible();

  const bare = await unsortedPage(as, await buildWorld());
  await expect(bare.getByText(/lorenzo seed --layer core/)).toBeVisible();
});
