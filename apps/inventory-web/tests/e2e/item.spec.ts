import { randomUUID } from 'node:crypto';
import { expect, test } from './support/fixtures.ts';
import { catalog, DESCRIPTIONS, packed } from './support/scenes.ts';

const itemPage = (tenantId: string, id: string) => `/item/?tenant=${tenantId}&id=${id}`;

test('a player reads the whole of an item they carry', async ({ world, as }) => {
  const { spellbook } = await packed(world, world.pia);
  const page = await as(world.pia);
  await page.goto(itemPage(world.tenantId, spellbook));

  await expect(page.getByRole('heading', { level: 1, name: 'Ornate Spellbook' })).toBeVisible();
  await expect(page.getByText('Gilded edges, a silver clasp')).toBeVisible();
  await expect(page.getByText('From Spellbook')).toBeVisible();
  await expect(page.getByText('From Book')).toBeVisible();
  await expect(page.getByRole('listitem').filter({ hasText: 'Magical' })).toBeVisible();
  // Reading is all a player does here.
  await expect(page.getByRole('button', { name: 'Edit description' })).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Tags' })).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Information' })).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Slug' })).toBeHidden();
});

test('a GM follows where a description comes from, up the prototypes', async ({ world, as }) => {
  const { spellbook } = await packed(world, world.pia);
  const page = await as(world.gm);
  await page.goto(itemPage(world.tenantId, spellbook));

  await page.getByText('From Spellbook').getByRole('link').click();
  await expect(page.getByRole('heading', { level: 1, name: 'Spellbook' })).toBeVisible();
  await expect(page.getByText(DESCRIPTIONS.book.slice(0, 30))).toBeVisible();
  const ancestry = page.getByRole('heading', { name: 'Ancestry' }).locator('..');
  await expect(ancestry.getByText('Book', { exact: true })).toBeVisible();
  const usedBy = page.getByRole('region', { name: 'Used as a prototype by' });
  await expect(usedBy.getByText('Ornate Spellbook')).toBeVisible();
});

test("opens an instance's page by its slug", async ({ world, as }) => {
  const { ornate } = await catalog(world);
  await world.instance(ornate, { owner: world.pia, slug: 'ashfangs-grimoire' });
  const page = await as(world.pia);
  await page.goto(`/item/?tenant=${world.tenantId}&slug=ashfangs-grimoire`);

  await expect(page.getByRole('heading', { level: 1, name: 'Ornate Spellbook' })).toBeVisible();
  await expect(page.getByText('ashfangs-grimoire')).toBeVisible();
});

test('copies its own link', async ({ world, as }) => {
  const { spellbook } = await packed(world, world.pia);
  const page = await as(world.pia);
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto(itemPage(world.tenantId, spellbook));

  await page.getByRole('button', { name: 'Copy link' }).click();
  await expect(page.getByRole('button', { name: 'Copied!' })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(page.url());
});

test('lists the descriptions that link to it, and the link leads here', async ({ world, as }) => {
  const { pouch } = await catalog(world);
  // The Backpack's description says [[Belt Pouch]]: a link once something holds that slug.
  await world.slug(pouch, 'belt-pouch');
  const page = await as(world.gm);
  await page.goto(itemPage(world.tenantId, pouch));

  const mentions = page.getByRole('region', { name: 'Mentioned in' });
  await mentions.getByRole('link', { name: 'Backpack' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Backpack' })).toBeVisible();
  await page.locator('#item-view').getByRole('link', { name: 'Belt Pouch' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Belt Pouch' })).toBeVisible();
});

test('says so when its link is incomplete, or leads nowhere', async ({ world, as }) => {
  const page = await as(world.pia);
  await page.goto(`/item/?tenant=${world.tenantId}`);
  await expect(
    page.getByText("This link is incomplete — it's missing a tenant or item."),
  ).toBeVisible();

  const nowhere = "There's no such item here, or it isn't one you can see.";
  await page.goto(itemPage(world.tenantId, randomUUID()));
  await expect(page.getByText(nowhere)).toBeVisible();
  const gm = await as(world.gm);
  await gm.goto(itemPage(world.tenantId, randomUUID()));
  await expect(gm.getByText(nowhere)).toBeVisible();
});
