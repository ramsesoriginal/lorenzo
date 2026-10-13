import { expect, test } from './support/fixtures.ts';
import { enterMode } from './support/modes.ts';

const url = (world: { tenantId: string }, id: string) =>
  `/being/?tenant=${world.tenantId}&id=${id}`;

// A 1x1 transparent PNG.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
);

test('a GM renames a being, writes its description and gives it a link name', async ({
  world,
  as,
}) => {
  const goblin = await world.npc('Goblin Chief');
  const page = await as(world.gm);
  await page.goto(url(world, goblin.entity_id));
  await enterMode(page, 'Edit');

  const name = page.locator('[data-name-edit]');
  await name.getByLabel('Name').fill('Goblin King');
  await name.getByRole('button', { name: 'Rename' }).click();
  await expect(page.getByRole('heading', { name: 'Goblin King', level: 1 })).toBeVisible();

  await page.getByRole('button', { name: 'Write a description' }).click();
  const form = page.locator('[data-description-edit] form');
  await form.getByLabel('Description').fill('Wears a *crown* of bottle caps.');
  await form.getByRole('button', { name: 'Save' }).click();
  await expect(page.locator('[data-being-view] em')).toHaveText('crown');

  const slug = page.locator('[data-slug-editor]');
  await slug.getByLabel('Link name').fill('goblin-king');
  await slug.getByRole('button', { name: 'Save link name' }).click();
  await expect(page.locator('[data-link-name]')).toHaveText('goblin-king');
  await expect(page).toHaveURL(/slug=goblin-king/);

  // It is what the API says, too: a reload by link name finds the renamed being.
  await page.goto(`/being/?tenant=${world.tenantId}&slug=goblin-king`);
  await expect(page.getByRole('heading', { name: 'Goblin King', level: 1 })).toBeVisible();
});

test('a GM sets a stat and a tag, and clears the stat again', async ({ world, as }) => {
  await world.defineStat('abilities', 'strength', 'int');
  await world.defineStat('tags', 'is_undead', 'bool');
  const goblin = await world.npc('Goblin Chief');
  const page = await as(world.gm);
  await page.goto(url(world, goblin.entity_id));
  await enterMode(page, 'Edit');

  const stats = page.locator('[data-stat-band]');
  await stats.getByLabel('Strength', { exact: true }).fill('14');
  await stats.getByLabel('Strength', { exact: true }).press('Enter');
  await expect(page.locator('[data-save-status]')).toHaveText('Saved.');
  await expect(stats.getByLabel('Strength', { exact: true })).toHaveValue('14');
  await expect(stats.getByRole('button', { name: 'Use inherited Strength' })).toBeVisible();

  const tags = page.locator('[data-tag-editor]');
  await tags.getByRole('group', { name: 'Undead' }).getByLabel('On').check();
  await expect(page.locator('[data-tag-chips] li')).toHaveText('Undead');

  await stats.getByRole('button', { name: 'Use inherited Strength' }).click();
  await expect(stats.getByLabel('Strength', { exact: true })).toHaveValue('');
});

test('a GM gives a being a picture, and takes it away', async ({ world, as }) => {
  const goblin = await world.npc('Goblin Chief');
  const page = await as(world.gm);
  await page.goto(url(world, goblin.entity_id));
  await enterMode(page, 'Edit');

  await expect(page.locator('[data-picture-figure]')).toBeHidden();
  await page.getByLabel('Picture file').setInputFiles({
    name: 'chief.png',
    mimeType: 'image/png',
    buffer: PNG,
  });
  await page.getByRole('button', { name: 'Use this picture' }).click();
  await expect(page.locator('[data-picture-figure] img')).toBeVisible();

  await page.getByRole('button', { name: 'Remove the picture' }).click();
  await expect(page.locator('[data-picture-figure]')).toBeHidden();
});

test('a picture that is not one is refused before it is sent', async ({ world, as }) => {
  const goblin = await world.npc('Goblin Chief');
  const page = await as(world.gm);
  await page.goto(url(world, goblin.entity_id));
  await enterMode(page, 'Edit');

  await page.getByLabel('Picture file').setInputFiles({
    name: 'chief.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('not a picture'),
  });
  await page.getByRole('button', { name: 'Use this picture' }).click();
  await expect(page.getByText("That file type won't work")).toBeVisible();
});

test('a player edits their own being, and is not offered a hand over', async ({ world, as }) => {
  const page = await as(world.pia);
  await page.goto(url(world, world.pia.character.entity_id));
  await enterMode(page, 'Edit');

  await page.getByRole('button', { name: 'Write a description' }).click();
  const form = page.locator('[data-description-edit] form');
  await form.getByLabel('Description').fill('Quiet.');
  await form.getByRole('button', { name: 'Save' }).click();
  await expect(page.locator('[data-being-view]')).toContainText('Quiet.');
  // Handing over is for a campaign's GM: a player is not offered it.
  await expect(page.locator('[data-hand-over]')).toBeHidden();
});
