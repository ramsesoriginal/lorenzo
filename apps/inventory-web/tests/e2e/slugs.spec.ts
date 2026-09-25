import type { Locator, Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import { DESCRIPTIONS } from './support/scenes.ts';
import type { World } from './support/world.ts';

const row = (list: Locator, name: string) =>
  list.getByRole('listitem').filter({ has: list.page().getByText(name, { exact: true }) });
const catalogList = (page: Page) =>
  page.getByRole('region', { name: 'Catalog' }).getByRole('list').first();
const slugRegion = (page: Page) => page.getByRole('region', { name: 'Slug' });

async function slugOf(world: World, id: string) {
  const entity = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: world.tenantId, entity_id: id } },
    }),
  );
  return entity.slug;
}

async function itemsNamed(world: World, name: string) {
  const found = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/items', {
      params: { path: { tenant_id: world.tenantId }, query: { q: name } },
    }),
  );
  return found.items;
}

test('a new item gets the slug its wikilinks look for', async ({ world, as }) => {
  const backpack = await world.item('Backpack', { description: DESCRIPTIONS.backpack });
  const page = await as(world.gm);
  await page.goto(`/items/?tenant=${world.tenantId}`);
  const form = page.getByRole('region', { name: 'New item' });

  await form.getByLabel('Name').fill('Pouch');
  await expect(form.getByLabel('Slug')).toHaveValue('pouch');
  // It follows the title the item is shown by.
  await form.getByLabel('Display title').fill('Belt Pouch');
  await expect(form.getByLabel('Slug')).toHaveValue('belt-pouch');
  await form.getByRole('button', { name: 'Create item' }).click();
  await expect(row(catalogList(page), 'Belt Pouch')).toBeVisible();

  const [pouch] = await itemsNamed(world, 'Pouch');
  expect(await slugOf(world, pouch?.entity_id as string)).toBe('belt-pouch');
  // The Backpack's [[Belt Pouch]] is a link now.
  await page.goto(`/item/?tenant=${world.tenantId}&id=${backpack}`);
  await page.locator('#item-view').getByRole('link', { name: 'Belt Pouch' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Belt Pouch' })).toBeVisible();
  await expect(page.getByText('belt-pouch', { exact: true })).toBeVisible();
});

test('stops following the title once the slug is edited', async ({ world, as }) => {
  const page = await as(world.gm);
  await page.goto(`/items/?tenant=${world.tenantId}`);
  const form = page.getByRole('region', { name: 'New item' });

  await form.getByLabel('Name').fill('Lantern');
  await expect(form.getByLabel('Slug')).toHaveValue('lantern');
  await form.getByLabel('Slug').fill('the-lamp');
  await form.getByLabel('Name').fill('Storm Lantern');
  await expect(form.getByLabel('Display title')).toHaveValue('Storm Lantern');
  await page.waitForTimeout(500);
  await expect(form.getByLabel('Slug')).toHaveValue('the-lamp');
});

test("refuses a slug that can't be one before creating anything", async ({ world, as }) => {
  const page = await as(world.gm);
  await page.goto(`/items/?tenant=${world.tenantId}`);
  const form = page.getByRole('region', { name: 'New item' });

  await form.getByLabel('Name').fill('Odd Thing');
  await form.getByLabel('Slug').fill('odd thing');
  await form.getByRole('button', { name: 'Create item' }).click();
  await expect(form.getByText(/A slug starts with a letter or digit/)).toBeVisible();
  expect(await itemsNamed(world, 'Odd Thing')).toEqual([]);
});

test('suggests the next free slug for an item, and shows the one it has', async ({ world, as }) => {
  const old = await world.item('Lantern');
  await world.describe(old, 'Brass, and dented.', 'Old Lantern');
  await world.slug(old, 'lantern');
  const lantern = await world.item('Lantern');
  const page = await as(world.gm);
  await page.goto(`/items/?tenant=${world.tenantId}`);

  const oldRow = row(catalogList(page), 'Old Lantern');
  await oldRow.getByRole('button', { name: 'Edit' }).click();
  await expect(oldRow.getByLabel('Slug')).toHaveValue('lantern');

  const newRow = row(catalogList(page), 'Lantern');
  await newRow.getByRole('button', { name: 'Edit' }).click();
  await expect(newRow.getByLabel('Slug')).toHaveValue('lantern-2');
  await newRow.getByRole('button', { name: 'Save' }).click();
  await expect.poll(() => slugOf(world, lantern)).toBe('lantern-2');
  expect(await slugOf(world, old)).toBe('lantern');
});

test("gives an instance a numbered slug on its page, and it's found by it", async ({
  world,
  as,
}) => {
  const lantern = await world.item('Lantern');
  const mine = await world.instance(lantern, { owner: world.pia });
  const page = await as(world.gm);
  await page.goto(`/item/?tenant=${world.tenantId}&id=${mine}`);

  await expect(slugRegion(page).getByLabel('Slug')).toHaveValue('lantern-1');
  await slugRegion(page).getByRole('button', { name: 'Save slug' }).click();
  await expect(slugRegion(page).getByRole('status')).toHaveText('Saved.');
  await expect(page.getByText('lantern-1', { exact: true })).toBeVisible();

  const pia = await as(world.pia);
  await pia.goto(`/item/?tenant=${world.tenantId}&slug=lantern-1`);
  await expect(pia.getByRole('heading', { level: 1, name: 'Lantern' })).toBeVisible();
  await expect(pia.getByRole('region', { name: 'Slug' })).toBeHidden();
});

test("a catalog item's slug opens its page, for those who can read the catalog", async ({
  world,
  as,
}) => {
  const pouch = await world.item('Belt Pouch');
  await world.slug(pouch, 'belt-pouch');
  const page = await as(world.gm);
  await page.goto(`/item/?tenant=${world.tenantId}&slug=belt-pouch`);
  await expect(page.getByRole('heading', { level: 1, name: 'Belt Pouch' })).toBeVisible();
  await expect(page.getByText('belt-pouch', { exact: true })).toBeVisible();

  const pia = await as(world.pia);
  await pia.goto(`/item/?tenant=${world.tenantId}&slug=belt-pouch`);
  await expect(
    pia.getByText("There's no such item here, or it isn't one you can see."),
  ).toBeVisible();
});

test('clears a slug, and refuses a bad or taken one', async ({ world, as }) => {
  const lantern = await world.item('Lantern');
  await world.slug(lantern, 'old-lamp');
  const other = await world.item('Torch');
  await world.slug(other, 'torch');
  const page = await as(world.gm);
  await page.goto(`/item/?tenant=${world.tenantId}&id=${lantern}`);
  const field = slugRegion(page).getByLabel('Slug');
  const save = slugRegion(page).getByRole('button', { name: 'Save slug' });
  const status = slugRegion(page).getByRole('status');

  await expect(field).toHaveValue('old-lamp');
  await field.fill('no spaces');
  await save.click();
  await expect(status).toContainText('only letters, digits');
  await field.fill('torch');
  await save.click();
  await expect(status).toHaveText('Another entity already uses “torch”.');
  expect(await slugOf(world, lantern)).toBe('old-lamp');

  await field.fill('');
  await save.click();
  await expect(status).toHaveText('Cleared.');
  expect(await slugOf(world, lantern)).toBeNull();
});

test('offers an instance a slug without giving it one', async ({ world, as }) => {
  const book = await world.item('Book');
  await world.instance(book, { slug: 'book-1' });
  const page = await as(world.gm);
  await page.goto(`/items/?tenant=${world.tenantId}`);

  const bookRow = row(catalogList(page), 'Book');
  await bookRow.getByRole('button', { name: 'Create instance' }).click();
  await expect(bookRow.getByLabel('Slug')).toHaveAttribute('placeholder', 'e.g. book-2');
  await expect(bookRow.getByLabel('Slug')).toHaveValue('');
  await bookRow.getByRole('button', { name: 'Create without assigning' }).click();
  await expect(bookRow.getByText('Created without an owner.')).toBeVisible();
  const unowned = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/item-instances/unowned', {
      params: { path: { tenant_id: world.tenantId } },
    }),
  );
  const slugs = unowned.groups.flatMap((group) => group.item_instances.map((i) => i.slug));
  expect(slugs.sort()).toEqual(['book-1', null]);
});
