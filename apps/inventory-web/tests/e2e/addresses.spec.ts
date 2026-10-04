// Slugs wherever an address takes an id (ADR 0135).
import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { catalog, packed } from './support/scenes.ts';
import { person } from './support/world.ts';

const column = (page: Page, name: string) => page.getByRole('region', { name });
const card = (page: Page, in_: string, name: string) =>
  column(page, in_).getByRole('button', { name, exact: true });
const itemsLink = (page: Page) =>
  page.getByRole('navigation', { name: 'Subpages' }).getByRole('link', { name: 'Items' });
const lastTenant = (page: Page) =>
  page.evaluate(() => window.localStorage.getItem('lorenzo:lastTenant'));

test("opens a board by the library's slug and the character's, and keeps them", async ({
  world,
  as,
}) => {
  await packed(world, world.pia);
  await world.slug(world.pia.character.entity_id, 'ashfang');
  const page = await as(world.pia);
  await page.evaluate(() => window.localStorage.removeItem('lorenzo:lastTenant'));
  const address = `/board/?tenant=${world.tenantSlug}&character=ashfang`;
  await page.goto(address);

  await expect(page.getByRole('heading', { name: world.tenantName })).toBeVisible();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Ashfang' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page).toHaveURL(address);
  // The header carries the library along as the address names it, and remembers its id.
  await expect(itemsLink(page)).toHaveAttribute('href', `/items/?tenant=${world.tenantSlug}`);
  await expect.poll(() => lastTenant(page)).toBe(world.tenantId);
  await page.goto('/items/');
  await expect(page).toHaveURL(`/items/?tenant=${world.tenantId}`);
});

test("opens a group's board by its slug, and picking another writes its id", async ({
  world,
  as,
}) => {
  const company = await world.group('The Company', [world.pia, world.oskar]);
  await world.slug(company, 'the-company');
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}&group=the-company`);

  await expect(page.getByText('Viewing what The Company holds.')).toBeVisible();
  await expect(page).toHaveURL(`/board/?tenant=${world.tenantId}&group=the-company`);
  await page.getByRole('link', { name: 'Ashfang' }).click();
  await expect(page).toHaveURL(
    `/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`,
  );
});

test("opens an item's page by the slug in its id", async ({ world, as }) => {
  const { pouch } = await catalog(world);
  await world.slug(pouch, 'belt-pouch');
  const page = await as(world.gm);
  const address = `/item/?tenant=${world.tenantSlug}&id=belt-pouch`;
  await page.goto(address);

  await expect(page.getByRole('heading', { level: 1, name: 'Belt Pouch' })).toBeVisible();
  await expect(page).toHaveURL(address);
});

test("links an item's dialog to its page by the slugs it has", async ({ world, as }) => {
  const { spellbook, pouch } = await packed(world, world.pia);
  await world.slug(spellbook, 'ornate-spellbook');
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  const link = page.getByRole('link', { name: 'View standalone page' });

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(link).toHaveAttribute(
    'href',
    `/item/?tenant=${world.tenantSlug}&slug=ornate-spellbook`,
  );
  await page.keyboard.press('Escape');

  await card(page, 'Equipped', 'Belt Pouch').click();
  await expect(link).toHaveAttribute('href', `/item/?tenant=${world.tenantSlug}&id=${pouch}`);
});

test('says so when a slug names nothing, or a library that is not hers', async ({ world, as }) => {
  const hilde = await person('Hilde', ['tenant_creator']);
  const elsewhere = await hilde.api.POST('/tenants', {
    body: { name: `Hilde's ${world.tenantId}` },
  });
  const page = await as(world.pia);

  for (const slug of ['no-such-library', elsewhere.data?.slug as string]) {
    await page.goto(`/board/?tenant=${slug}`);
    await expect(page.getByText(`There's no library “${slug}” you can see.`)).toBeVisible();
  }
  // What she had open is still what's remembered.
  expect(await lastTenant(page)).toBe(world.tenantId);

  await page.goto(`/item/?tenant=${world.tenantId}&id=no-such-item`);
  await expect(
    page.getByText("There's no such item here, or it isn't one you can see."),
  ).toBeVisible();
});

test('a GM browses a being by its slug', async ({ world, as }) => {
  await world.slug(world.oskar.character.entity_id, 'brisk');
  const page = await as(world.gm);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('tab', { name: 'Browse a being' }).click();
  const box = page.getByLabel("Being's id or slug");
  const view = page.getByRole('button', { name: 'View', exact: true });

  await box.fill('brisk');
  await view.click();
  await expect(page.getByText("Viewing Brisk's inventory.")).toBeVisible();
  await expect(column(page, 'Equipped')).toBeVisible();

  await box.fill('nobody');
  await view.click();
  await expect(page.getByText('Nothing here has the slug “nobody”.')).toBeVisible();
});

test('gives something to a being named by its slug', async ({ world, as }) => {
  await packed(world, world.pia);
  await world.slug(world.oskar.character.entity_id, 'brisk');
  const page = await as(world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await page.getByLabel("Being's id or slug").filter({ visible: true }).fill('brisk');
  await page.getByRole('button', { name: 'Use ID' }).filter({ visible: true }).click();
  await expect(page.getByText('Given to Brisk.')).toBeVisible();
  await expect(card(page, 'Backpack', "Ornate Spellbook Brisk's")).toBeVisible();
});
