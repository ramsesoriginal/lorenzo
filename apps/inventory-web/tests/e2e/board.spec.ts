import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
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

/** Picks `name` in a being search, as every give and assign panel offers one. */
async function pickBeing(page: Page, name: string) {
  await page.getByLabel('Search beings').filter({ visible: true }).fill(name);
  await page.getByRole('option').getByRole('button', { name }).click();
}

test('shows each container as a column of cards', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await expect(card(page, 'Ashfang', 'Backpack')).toBeVisible();
  await expect(card(page, 'Ashfang', 'Belt Pouch')).toBeVisible();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();
});

test('picks a character from the strip', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('button', { name: 'Ashfang' }).click();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
  await expect(page).toHaveURL(
    `/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`,
  );
});

test('says so when a character carries nothing', async ({ world, as }) => {
  const page = await boardOf(as, world, world.oskar);
  await expect(page.getByText("Brisk isn't carrying anything yet.")).toBeVisible();
});

test('opens an item to show all of it, with what it inherits labelled', async ({ world, as }) => {
  await packed(world, world.pia);
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

  // A player can't open catalog items (ADR 0032), so where it comes from isn't a link.
  await expect(detail.getByText('From Spellbook').getByRole('link')).toHaveCount(0);
});

test('closes the item with Escape', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
});

test('gives an item to another character, and takes it back with undo', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await pickBeing(page, 'Brisk');
  await expect(page.getByText('Given to Brisk.')).toBeVisible();
  // It isn't hers any more, so there's nothing left to show.
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeHidden();
  // Giving changes who owns it, not where it is (ADR 0051): it's still in Pia's backpack.
  expect(await world.carried(world.oskar)).toEqual(['Backpack: Ornate Spellbook']);

  await expect(page.getByText('Gave Ornate Spellbook to Brisk.')).toBeVisible();
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(page.getByRole('button', { name: 'Ornate Spellbook', exact: true })).toBeVisible();
  expect(await world.carried(world.oskar)).toEqual([]);
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

  await card(page, 'Belt Pouch', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('button', { name: 'Remove from container' }).click();
  await expect(card(page, 'Ashfang', 'Ornate Spellbook')).toBeVisible();
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

  await card(page, 'Backpack', 'Ornate Spellbook').dragTo(column(page, 'Ashfang'));
  await expect(card(page, 'Ashfang', 'Ornate Spellbook')).toBeVisible();
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

test('offers no split for a single item', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(page.getByRole('button', { name: 'Split…' })).toBeDisabled();
});

test('searches the board by name', async ({ world, as }) => {
  await packed(world, world.pia);
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

test('a player gets no GM tools', async ({ world, as }) => {
  const page = await boardOf(as, world, world.pia);
  await expect(page.getByRole('button', { name: 'Ashfang' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Manage items (GM)' })).toBeHidden();
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
  await expect(page.getByRole('link', { name: 'Manage items (GM)' })).toBeHidden();
  await page.goto(`/items/?tenant=${world.tenantId}`);
  await expect(page.getByText('This page is for GMs only.')).toBeVisible();
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

  await page.getByRole('link', { name: 'Manage items (GM)' }).click();
  await expect(page).toHaveURL(`/items/?tenant=${world.tenantId}`);
});
