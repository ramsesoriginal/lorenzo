import { INVENTORY_URL } from './support/env.ts';
import { expect, test } from './support/fixtures.ts';

test('a being’s page shows its description, stats, tags, players and inventory', async ({
  world,
  as,
}) => {
  const strength = await world.defineStat('abilities', 'strength', 'int');
  await world.setStat(world.pia.character.entity_id, strength.id, 17);
  await world.describe(world.pia.character.entity_id, 'A **tall** knight of the [[Brisk]] line.');
  await world.carry(world.pia.character, 'Longsword');
  await world.carry(world.pia.character, 'Torch');

  const page = await as(world.gm);
  await page.goto(`/being/?tenant=${world.tenantId}&id=${world.pia.character.entity_id}`);

  await expect(page.getByRole('heading', { name: 'Ashfang', level: 1 })).toBeVisible();
  await expect(page.locator('[data-kind]')).toHaveText('Character');
  await expect(page.locator('[data-being-view] strong')).toHaveText('tall');
  await expect(page.locator('[data-stat-band] .stat-label')).toHaveText('Strength');
  await expect(page.locator('[data-stat-band] .stat-value')).toHaveText('17');

  // Who plays it: Pia, as the owner, named because Gwen GMs the campaign.
  const people = page.locator('[data-people] li');
  await expect(people).toHaveCount(1);
  await expect(people).toContainText('Pia');
  await expect(people).toContainText('Owner');
  await expect(people).toContainText('in The Sunken Crown');

  // What it carries, and the way to its board.
  await expect(page.locator('[data-inventory]')).toContainText('2 items');
  await expect(page.locator('[data-inventory] li')).toHaveText(['Longsword', 'Torch']);
  await expect(page.getByRole('link', { name: 'Open the inventory board' })).toHaveAttribute(
    'href',
    `${INVENTORY_URL}/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`,
  );
});

test('an NPC says nobody plays it, and is addressed by its link name', async ({ world, as }) => {
  const goblin = await world.npc('Goblin Chief');
  await world.slug(goblin.entity_id, 'goblin-chief');
  const page = await as(world.gm);

  await page.goto(`/being/?tenant=${world.tenantSlug}&slug=goblin-chief`);
  await expect(page.getByRole('heading', { name: 'Goblin Chief', level: 1 })).toBeVisible();
  await expect(page.locator('[data-kind]')).toHaveText('NPC');
  await expect(page.locator('[data-people]')).toContainText('Nobody plays this being');
  await expect(page.locator('[data-link-name]')).toHaveText('goblin-chief');

  // Reached by id, the address becomes the link name.
  await page.goto(`/being/?tenant=${world.tenantId}&id=${goblin.entity_id}`);
  await expect(page.locator('[data-link-name]')).toHaveText('goblin-chief');
  await expect(page).toHaveURL(/slug=goblin-chief/);
});

test('something that is not a being, or not there, says so', async ({ world, as }) => {
  const page = await as(world.gm);

  await page.goto(`/being/?tenant=${world.tenantId}&slug=nothing-here`);
  await expect(page.locator('#status')).toContainText("There's no such being here");

  await page.goto(`/being/?tenant=${world.tenantId}`);
  await expect(page.locator('#status')).toContainText('missing a library or a being');
});

test('the list links to a being’s page', async ({ world, as }) => {
  const page = await as(world.pia);

  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await page.getByRole('link', { name: 'Brisk' }).click();
  await expect(page.getByRole('heading', { name: 'Brisk', level: 1 })).toBeVisible();
  // A player of another character is not offered Edit, nor a note to add.
  await expect(
    page.locator('[data-sheet-head] [data-mode-switch] input[value="edit"]'),
  ).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Add a note' })).toBeHidden();
});
