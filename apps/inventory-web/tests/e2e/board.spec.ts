import type { Page } from '@playwright/test';
import { expect, readOnly, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import { type Person, type Player, person, type World } from './support/world.ts';

type As = (who: Person) => Promise<Page>;

/** `player`'s board, logged in as them. */
async function boardOf(as: As, world: World, player: Player): Promise<Page> {
  const page = await as(player);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${player.character.entity_id}`);
  return page;
}

const column = (page: Page, name: string) => page.getByRole('region', { name });
const card = (page: Page, in_: string, name: string) =>
  column(page, in_).getByRole('button', { name, exact: true });
/** The header's link to the current tenant's catalog. */
const itemsLink = (page: Page) =>
  page.getByRole('navigation', { name: 'Subpages' }).getByRole('link', { name: 'Items' });

/** Picks `name` in a being search, as every give and assign panel offers one. */
async function pickBeing(page: Page, name: string) {
  await page.getByLabel('Search beings').filter({ visible: true }).fill(name);
  await page.getByRole('option').getByRole('button', { name }).click();
}

readOnly('shows each container as a column of cards', async ({ world, as }) => {
  const page = await boardOf(as, world, world.pia);

  await expect(card(page, 'Equipped', 'Backpack')).toBeVisible();
  await expect(card(page, 'Equipped', 'Belt Pouch')).toBeVisible();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();
});

readOnly('picks a character from the list', async ({ world, as }) => {
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('link', { name: 'Ashfang' }).click();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
  await expect(page).toHaveURL(
    `/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`,
  );
});

readOnly('shows Equipped even when a character carries nothing', async ({ world, as }) => {
  const page = await boardOf(as, world, world.oskar);
  await expect(column(page, 'Equipped')).toContainText('Nothing equipped.');
});

test("keeps what isn't carried apart, and gives an empty container a column", async ({
  world,
  as,
}) => {
  await packed(world, world.pia);
  const chest = await world.item('Treasure Chest', { tags: ['is_container'] });
  await world.instance(chest, { owner: world.pia });
  const page = await boardOf(as, world, world.pia);

  // Hers, but in no container: not carried, so not equipped (RFC 0031).
  await expect(card(page, 'Not carried', 'Treasure Chest')).toBeVisible();
  await expect(card(page, 'Equipped', 'Treasure Chest')).toHaveCount(0);
  // An empty container is somewhere to drop, carried or not.
  await expect(column(page, 'Belt Pouch')).toContainText('This container is empty.');
  await expect(column(page, 'Treasure Chest')).toContainText('This container is empty.');
  await expect(column(page, 'Treasure Chest')).toContainText('Not carried');
  // The two places every board has.
  await expect(column(page, 'Equipped')).toHaveClass(/glow-canonical/);
  await expect(column(page, 'Not carried')).toHaveClass(/glow-canonical/);

  // Picked up, its column says so at once (ADR 0134).
  await card(page, 'Not carried', 'Treasure Chest').dragTo(column(page, 'Equipped'));
  await expect(card(page, 'Equipped', 'Treasure Chest')).toBeVisible();
  await expect(column(page, 'Treasure Chest')).not.toContainText('Not carried');
});

test("says who has a thing of hers that she doesn't carry", async ({ world, as }) => {
  await packed(world, world.pia);
  const chest = await world.item('Treasure Chest', { tags: ['is_container'] });
  await world.instance(chest, { owner: world.pia, container: world.oskar.character.entity_id });
  const page = await boardOf(as, world, world.pia);

  await expect(column(page, 'Treasure Chest')).toContainText('Not carried, with Brisk');
});

readOnly("opens a player's only character by itself", async ({ world, as }) => {
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);

  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
  await expect(page).toHaveURL(
    `/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`,
  );
});

test("doesn't look inside someone else's bag she carries, until something of hers is in it", async ({
  world,
  as,
}) => {
  const { items } = await packed(world, world.pia);
  const satchel = await world.item('Satchel', { tags: ['is_container'] });
  const bag = await world.instance(satchel, {
    owner: world.oskar,
    container: world.pia.character.entity_id,
  });
  await world.instance(items.book, { owner: world.oskar, container: bag });
  const page = await boardOf(as, world, world.pia);

  await expect(column(page, 'Satchel')).toContainText('Contents not shown.');
  await expect(card(page, 'Satchel', "Book Brisk's")).toHaveCount(0);

  await card(page, 'Backpack', 'Ornate Spellbook').dragTo(column(page, 'Satchel'));
  await expect.poll(() => world.carried(world.pia)).toContain('Satchel: Ornate Spellbook');
  await page.reload();
  await expect(card(page, 'Satchel', "Book Brisk's")).toBeVisible();
});

test("marks what isn't hers, and shows his things held elsewhere", async ({ world, as }) => {
  const { items, backpack } = await packed(world, world.pia);
  // Brisk's book, in Ashfang's backpack.
  await world.instance(items.book, { owner: world.oskar, container: backpack });

  const pia = await boardOf(as, world, world.pia);
  await expect(card(pia, 'Backpack', "Book Brisk's")).toBeVisible();
  // Her own things carry no mark.
  await expect(card(pia, 'Backpack', 'Ornate Spellbook')).toBeVisible();

  const oskar = await boardOf(as, world, world.oskar);
  // In the same row as what he carries, its note says who has it (ADR 0134), and it's
  // marked read-only.
  await expect(column(oskar, 'Backpack')).toContainText('Not carried, with Ashfang');
  await expect(column(oskar, 'Backpack')).toHaveClass(/board-column--read-only/);
  await expect(card(oskar, 'Backpack', 'Book')).toBeVisible();
  // Only what's his: her spellbook in the same backpack isn't his to see here.
  await expect(card(oskar, 'Backpack', 'Ornate Spellbook')).toHaveCount(0);
  await expect(column(oskar, 'Backpack')).toContainText('Other contents not shown.');
  await expect(column(oskar, 'Equipped')).toContainText('Nothing equipped.');

  // Her backpack is read-only on his board (ADR 0131): his book isn't moved from here.
  await expect(card(oskar, 'Backpack', 'Book')).toHaveAttribute('draggable', 'false');
  await card(oskar, 'Backpack', 'Book').click();
  await expect(oskar.getByRole('button', { name: 'Give to…' })).toBeVisible();
  await expect(oskar.getByRole('button', { name: 'Move to…' })).toBeHidden();
});

readOnly(
  'opens an item to show all of it, with what it inherits labelled',
  async ({ world, as }) => {
    const page = await boardOf(as, world, world.pia);

    // A card is a button, so the keyboard opens it too.
    await card(page, 'Backpack', 'Ornate Spellbook').focus();
    await page.keyboard.press('Enter');
    const detail = page.getByRole('dialog');
    await expect(detail.getByRole('heading', { name: 'Ornate Spellbook' })).toBeVisible();
    await expect(detail.getByText('Gilded edges, a silver clasp')).toBeVisible();
    await expect(detail.getByText('From Spellbook')).toBeVisible();
    await expect(detail.getByText("written in the caster's own notation")).toBeVisible();
    await expect(detail.getByText('From Book')).toBeVisible();
    await expect(detail.getByText('Pages bound between two covers')).toBeVisible();
    await expect(detail.getByRole('term').filter({ hasText: 'Price' })).toBeVisible();
    await expect(detail.getByRole('definition').filter({ hasText: '250' })).toBeVisible();
    await expect(detail.getByRole('term').filter({ hasText: 'Weight' })).toBeVisible();
    await expect(detail.getByRole('listitem').filter({ hasText: 'Magical' })).toBeVisible();

    // Any participant opens a catalog item (ADR 0116), so where it comes from is a link.
    await detail.getByText('From Spellbook').getByRole('link').click();
    await expect(page.getByRole('heading', { level: 1, name: 'Spellbook' })).toBeVisible();
  },
);

readOnly('closes the item with Escape', async ({ world, as }) => {
  const page = await boardOf(as, world, world.pia);
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
});

test('gives an item to another character, with no Undo that would fail', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await pickBeing(page, 'Brisk');
  await expect(page.getByText('Given to Brisk.')).toBeVisible();
  await expect(page.getByRole('dialog')).toBeHidden();
  // Giving changes who owns it, not where it is (ADR 0051): still in her backpack, now his.
  await expect(card(page, 'Backpack', "Ornate Spellbook Brisk's")).toBeVisible();
  expect(await world.carried(world.oskar)).toEqual(['Backpack: Ornate Spellbook']);
  // Taking it back would be giving away Brisk's book, which only he or a GM may (ADR 0124).
  await expect(page.getByRole('button', { name: 'Undo' })).toBeHidden();
});

test('gives part of a stack', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Arrow ×3').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await page.getByLabel('How many? (of 3, blank for all)').fill('1');
  await pickBeing(page, 'Brisk');
  await expect(card(page, 'Backpack', 'Arrow ×2')).toBeVisible();
  expect(await world.carried(world.oskar)).toEqual(['Backpack: Arrow']);
});

test('moves an item into another container and out again', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Belt Pouch' }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(card(page, 'Belt Pouch', 'Ornate Spellbook')).toBeVisible();

  // Equipping is moving it into Ashfang's hands.
  await card(page, 'Belt Pouch', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Equipped', exact: true }).click();
  await expect(card(page, 'Equipped', 'Ornate Spellbook')).toBeVisible();
  expect(await world.carried(world.pia)).toContain('(none): Ornate Spellbook');
});

test('undoes a move', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Belt Pouch' }).click();
  await expect(card(page, 'Belt Pouch', 'Ornate Spellbook')).toBeVisible();
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
});

test('drags an item out of its container', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').dragTo(column(page, 'Equipped'));
  await expect(card(page, 'Equipped', 'Ornate Spellbook')).toBeVisible();
  await expect.poll(() => world.carried(world.pia)).toContain('(none): Ornate Spellbook');
});

test('splits a stack, then merges it back', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Arrow ×3').click();
  await page.getByRole('button', { name: 'Split…' }).click();
  await page.getByLabel('Split off how many? (of 3)').fill('1');
  await page.getByRole('button', { name: 'Split', exact: true }).click();
  await expect(card(page, 'Backpack', 'Arrow ×2')).toBeVisible();
  await expect(card(page, 'Backpack', 'Arrow')).toBeVisible();

  await card(page, 'Backpack', 'Arrow').click();
  await page.getByRole('button', { name: 'Merge into…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Arrow ×2' }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();
  expect(await world.carried(world.pia)).toContain('Backpack: Arrow ×3');
});

readOnly('offers no split for a single item', async ({ world, as }) => {
  const page = await boardOf(as, world, world.pia);
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(page.getByRole('button', { name: 'Split…' })).toBeDisabled();
});

readOnly('searches the board by name', async ({ world, as }) => {
  const page = await boardOf(as, world, world.pia);

  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();
  await page.getByRole('searchbox', { name: 'Search this inventory' }).fill('spell');
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeHidden();
});

test('gives several selected items at once', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await page.getByRole('button', { name: 'Select items' }).click();
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await card(page, 'Backpack', 'Arrow ×3').click();
  await expect(card(page, 'Backpack', 'Arrow ×3')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('2 selected')).toBeVisible();
  await page.getByRole('button', { name: 'Give selected to…' }).click();
  await pickBeing(page, 'Brisk');
  await expect(page.getByText('Gave 2 item(s) to Brisk.')).toBeVisible();
  await expect
    .poll(() => world.carried(world.oskar))
    .toEqual(['Backpack: Arrow ×3', 'Backpack: Ornate Spellbook']);
});

test('moves a selection by dragging one of it', async ({ world, as }) => {
  const { items, pouch } = await packed(world, world.pia);
  // Something in the pouch, so it has a column to drop onto.
  await world.instance(items.book, { owner: world.pia, container: pouch });
  const page = await boardOf(as, world, world.pia);

  await page.getByRole('button', { name: 'Select items' }).click();
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await card(page, 'Backpack', 'Arrow ×3').click();
  await card(page, 'Backpack', 'Arrow ×3').dragTo(column(page, 'Belt Pouch'));
  await expect(card(page, 'Belt Pouch', 'Ornate Spellbook')).toBeVisible();
  await expect(card(page, 'Belt Pouch', 'Arrow ×3')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Select items' })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
  await expect
    .poll(() => world.carried(world.pia))
    .toEqual([
      '(none): Backpack',
      '(none): Belt Pouch',
      'Belt Pouch: Arrow ×3',
      'Belt Pouch: Book',
      'Belt Pouch: Ornate Spellbook',
    ]);
});

readOnly('a player gets no GM tools', async ({ world, as }) => {
  const page = await boardOf(as, world, world.pia);
  await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();
  await expect(itemsLink(page)).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Browse a being' })).toBeHidden();
});

test('someone who GMs another tenant is only a player here', async ({ world, as }) => {
  const hilde = await person('Hilde', ['tenant_creator']);
  const elsewhere = await hilde.api.POST('/tenants', {
    body: { name: `Hilde's ${world.tenantId}` },
  });
  const tenantId = elsewhere.data?.id as string;
  const campaign = await hilde.api.POST('/tenants/{tenant_id}/campaigns', {
    params: { path: { tenant_id: tenantId } },
    body: {
      name: 'Elsewhere',
      game_system: 'Any',
      slug: 'elsewhere',
      description: '',
      secret: false,
    },
  });
  await hilde.api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
    params: {
      path: {
        tenant_id: tenantId,
        campaign_id: campaign.data?.id as string,
        user_id: hilde.userId,
      },
    },
  });
  await world.gm.api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
    params: { path: { tenant_id: world.tenantId, campaign_id: world.campaignId } },
    body: { user_id: hilde.userId },
  });

  const page = await as(hilde);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await expect(page.getByRole('heading', { name: world.tenantName })).toBeVisible();
  await itemsLink(page).click();
  await expect(page.getByRole('region', { name: 'Catalog' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'New item' })).toBeHidden();
});

test('a GM browses any being, and what nobody owns', async ({ world, as }) => {
  const { items } = await packed(world, world.pia);
  await world.instance(items.book);
  const page = await as(world.gm);
  await page.goto(`/board/?tenant=${world.tenantId}`);

  await page.getByRole('tab', { name: 'Browse a being' }).click();
  await pickBeing(page, 'Ashfang');
  await expect(page.getByText("Viewing Ashfang's inventory.")).toBeVisible();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();

  await page.getByRole('tab', { name: 'Unowned items' }).click();
  await expect(page.getByText('Viewing unowned items.')).toBeVisible();
  await expect(card(page, 'Unowned', 'Book')).toBeVisible();

  await itemsLink(page).click();
  await expect(page).toHaveURL(`/items/?tenant=${world.tenantId}`);
});
