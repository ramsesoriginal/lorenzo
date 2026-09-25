import type { Locator, Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import { catalog, packed } from './support/scenes.ts';
import type { World } from './support/world.ts';

async function manageItems(as: (who: World['gm']) => Promise<Page>, world: World) {
  const page = await as(world.gm);
  await page.goto(`/items/?tenant=${world.tenantId}`);
  return page;
}

/** The row of a list whose own title is exactly `name`, not merely containing it. */
const row = (list: Locator, name: string) =>
  list.getByRole('listitem').filter({ has: list.page().getByText(name, { exact: true }) });

const catalogList = (page: Page) =>
  page.getByRole('region', { name: 'Catalog' }).getByRole('list').first();

async function entity(world: World, id: string) {
  return ok(
    world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: world.tenantId, entity_id: id } },
    }),
  );
}

test('a player gets the public catalog, to look items up, and nothing to change', async ({
  world,
  as,
}) => {
  await world.item('Robe', { public: true });
  await world.item('Backpack', { public: true });
  await world.item('Crown of Ash');
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('link', { name: 'Catalog' }).click();

  await expect(page).toHaveTitle('Catalog — Lorenzo');
  await expect(page.getByText('Everything your GMs have put in the public catalog.')).toBeVisible();
  await expect(row(catalogList(page), 'Robe')).toBeVisible();
  await expect(row(catalogList(page), 'Backpack')).toBeVisible();
  await expect(row(catalogList(page), 'Crown of Ash')).toBeHidden();
  await expect(page.getByRole('region', { name: 'New item' })).toBeHidden();
  await expect(page.getByRole('region', { name: 'Instances' })).toBeHidden();
  await expect(row(catalogList(page), 'Robe').getByRole('button')).toHaveCount(0);

  await page.getByRole('searchbox', { name: 'Search the item catalog' }).fill('back');
  await expect(row(catalogList(page), 'Robe')).toBeHidden();
  await row(catalogList(page), 'Backpack').getByRole('link', { name: 'View' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Backpack' })).toBeVisible();
});

test('a GM puts an item in the public catalog, and takes it out again', async ({ world, as }) => {
  const page = await manageItems(as, world);
  const form = page.getByRole('region', { name: 'New item' });
  await form.getByLabel('Name').fill('Robe');
  await form.getByLabel('In the public catalog').check();
  await form.getByRole('button', { name: 'Create item' }).click();

  const robeRow = row(catalogList(page), 'Robe');
  await expect(robeRow.getByText('Public', { exact: true })).toBeVisible();
  const [robe] = (
    await ok(
      world.gm.api.GET('/tenants/{tenant_id}/items', {
        params: { path: { tenant_id: world.tenantId }, query: { q: 'Robe' } },
      }),
    )
  ).items;
  expect(robe?.in_public_catalog).toBe(true);

  await robeRow.getByRole('button', { name: 'Edit' }).click();
  await expect(robeRow.getByLabel('In the public catalog')).toBeChecked();
  await robeRow.getByLabel('In the public catalog').uncheck();
  await robeRow.getByRole('button', { name: 'Save' }).click();
  await expect(robeRow.getByLabel('Name')).toBeHidden();
  await expect(row(catalogList(page), 'Robe').getByText('Public', { exact: true })).toBeHidden();
  expect((await entity(world, robe?.entity_id as string)).name).toBe('Robe');
  const pia = await as(world.pia);
  await pia.goto(`/items/?tenant=${world.tenantId}`);
  await expect(pia.getByText('No items match.')).toBeVisible();
});

test('creates an item with parents, a description, and a display title', async ({ world, as }) => {
  const { spellbook } = await catalog(world);
  const page = await manageItems(as, world);
  const form = page.getByRole('region', { name: 'New item' });

  await form.getByLabel('Name').fill('Grimoire');
  // The display title follows the name until it's edited.
  await expect(form.getByLabel('Display title')).toHaveValue('Grimoire');
  await form.getByLabel('Search items to inherit from').fill('Spellb');
  await form.getByRole('option').getByRole('button', { name: 'Spellbook', exact: true }).click();
  await expect(form.getByRole('listitem').filter({ hasText: 'Spellbook' })).toBeVisible();
  await form.getByLabel('Display title').fill('Grimoire of Ash');
  await form.getByRole('textbox', { name: 'Description' }).fill('Bound in ash-grey hide.');
  await form.getByRole('button', { name: 'Create item' }).click();

  await expect(row(catalogList(page), 'Grimoire of Ash')).toBeVisible();
  await expect(form.getByLabel('Name')).toHaveValue('');
  const items = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/items', {
      params: { path: { tenant_id: world.tenantId }, query: { q: 'Grimoire' } },
    }),
  );
  const created = await entity(world, items.items[0]?.entity_id as string);
  expect(created.name).toBe('Grimoire');
  expect(created.prototypes.map((p) => p.id)).toEqual([spellbook]);
});

test('edits an item: the name field holds its name, not its display title', async ({
  world,
  as,
}) => {
  const lantern = await world.item('Lantern');
  await world.describe(lantern, 'Shuttered.', 'Hooded Lantern');
  const page = await manageItems(as, world);

  const lanternRow = row(catalogList(page), 'Hooded Lantern');
  await lanternRow.getByRole('button', { name: 'Edit' }).click();
  await expect(lanternRow.getByLabel('Name')).toHaveValue('Lantern');
  await expect(lanternRow.getByLabel('Display title')).toHaveValue('Hooded Lantern');
  await lanternRow.getByLabel('Name').fill('Storm Lantern');
  await lanternRow.getByRole('textbox', { name: 'Description' }).fill('Shuttered, and oiled.');
  await lanternRow.getByRole('button', { name: 'Save' }).click();

  // Saving closes the panel; the row still shows the display title.
  await expect(lanternRow.getByLabel('Name')).toBeHidden();
  await expect(row(catalogList(page), 'Hooded Lantern')).toBeVisible();
  const saved = await entity(world, lantern);
  expect(saved.name).toBe('Storm Lantern');
  expect(saved.information[0]?.payloads[0]).toMatchObject({ content: 'Shuttered, and oiled.' });
});

test('shows what is built on an item', async ({ world, as }) => {
  await catalog(world);
  const page = await manageItems(as, world);

  const bookRow = row(catalogList(page), 'Book');
  await bookRow.getByRole('button', { name: 'Edit' }).click();
  const usedBy = bookRow.getByText('Used as a prototype by').locator('..');
  await expect(usedBy.getByText('Spellbook', { exact: true })).toBeVisible();
  await expect(usedBy.getByText('Ornate Spellbook', { exact: true })).toBeVisible();
});

test('searches the catalog', async ({ world, as }) => {
  await catalog(world);
  const page = await manageItems(as, world);

  await expect(row(catalogList(page), 'Arrow')).toBeVisible();
  await page.getByRole('searchbox', { name: 'Search the item catalog' }).fill('spell');
  await expect(row(catalogList(page), 'Ornate Spellbook')).toBeVisible();
  await expect(row(catalogList(page), 'Arrow')).toBeHidden();
});

test('deletes an item after asking', async ({ world, as }) => {
  await catalog(world);
  const page = await manageItems(as, world);

  page.once('dialog', (dialog) => dialog.accept());
  await row(catalogList(page), 'Arrow').getByRole('button', { name: 'Delete' }).click();
  await expect(row(catalogList(page), 'Arrow')).toBeHidden();
  await page.reload();
  await expect(row(catalogList(page), 'Book')).toBeVisible();
  await expect(row(catalogList(page), 'Arrow')).toBeHidden();
});

test('creates instances: for a character, with a slug, and for nobody', async ({ world, as }) => {
  await catalog(world);
  const page = await manageItems(as, world);

  const bookRow = row(catalogList(page), 'Book');
  await bookRow.getByRole('button', { name: 'Create instance' }).click();
  await bookRow.getByLabel('Slug').fill('ashfangs-book');
  await bookRow.getByLabel('Search beings').fill('Ashf');
  await bookRow.getByRole('option').getByRole('button', { name: 'Ashfang' }).click();
  await expect(bookRow.getByText('Created and assigned to Ashfang.')).toBeVisible();
  expect(await world.carried(world.pia)).toEqual(['(none): Book']);
  const bySlug = await world.gm.api.GET('/tenants/{tenant_id}/item-instances/by-slug/{slug}', {
    params: { path: { tenant_id: world.tenantId, slug: 'ashfangs-book' } },
  });
  expect(bySlug.data?.owner_entity_id).toBe(world.pia.character.entity_id);

  const arrowRow = row(catalogList(page), 'Arrow');
  await arrowRow.getByRole('button', { name: 'Create instance' }).click();
  await arrowRow.getByRole('button', { name: 'Create without assigning' }).click();
  await expect(arrowRow.getByText('Created without an owner.')).toBeVisible();
  const unowned = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/item-instances/unowned', {
      params: { path: { tenant_id: world.tenantId } },
    }),
  );
  expect(unowned.groups.flatMap((g) => g.item_instances.map((i) => i.title))).toEqual(['Arrow']);
});

test("browses a being's instances, and reassigns, unassigns, and deletes them", async ({
  world,
  as,
}) => {
  await packed(world, world.pia);
  const page = await manageItems(as, world);
  const instances = page.getByRole('region', { name: 'Instances' });

  await page.getByRole('combobox', { name: "View a being's inventory" }).fill('Ashf');
  await instances.getByRole('option').getByRole('button', { name: 'Ashfang' }).click();
  await expect(instances.getByText("Viewing Ashfang's inventory.")).toBeVisible();

  await row(instances, 'Ornate Spellbook').getByRole('button', { name: 'Reassign' }).click();
  await instances.getByLabel('Search beings').fill('Bri');
  await instances.getByRole('option').getByRole('button', { name: 'Brisk' }).click();
  await expect(instances.getByText('Reassigned to Brisk.')).toBeVisible();
  await expect(row(instances, 'Ornate Spellbook')).toBeHidden();

  await row(instances, 'Belt Pouch').getByRole('button', { name: 'Unassign' }).click();
  await expect(row(instances, 'Belt Pouch')).toBeHidden();

  page.once('dialog', (dialog) => dialog.accept());
  await row(instances, 'Arrow ×3').getByRole('button', { name: 'Delete' }).click();
  await expect(row(instances, 'Arrow ×3')).toBeHidden();

  expect(await world.carried(world.pia)).toEqual(['(none): Backpack']);
  expect(await world.carried(world.oskar)).toEqual(['Backpack: Ornate Spellbook']);
});
