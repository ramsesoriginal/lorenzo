import { expect, test } from './support/fixtures.ts';
import { enterMode } from './support/modes.ts';

const url = (world: { tenantId: string }, id: string) =>
  `/being/?tenant=${world.tenantId}&id=${id}`;

// The sections of a being's sheet, top to bottom, as the page draws them.
const order = (page: import('@playwright/test').Page) =>
  page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('[data-sheet-main] > [data-section]')]
      .sort((a, b) => Number(a.style.order) - Number(b.style.order))
      .map((section) => section.dataset.section),
  );

test('Read puts the prose first, Play the numbers first, and Edit keeps Read’s order', async ({
  world,
  as,
}) => {
  const strength = await world.defineStat('abilities', 'strength', 'int');
  await world.setStat(world.pia.character.entity_id, strength.id, 17);
  const page = await as(world.gm);
  await page.goto(url(world, world.pia.character.entity_id));

  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', 'read');
  expect(await order(page)).toEqual(['about', 'notes', 'stats', 'inventory']);

  await enterMode(page, 'Play');
  expect(await order(page)).toEqual(['stats', 'inventory', 'notes', 'about']);
  await expect(page.locator('[data-stat-band]').getByRole('textbox')).toHaveCount(0);

  await enterMode(page, 'Edit');
  expect(await order(page)).toEqual(['about', 'notes', 'stats', 'inventory']);
  // Every value is a field in Edit.
  await expect(
    page.locator('[data-stat-band]').getByLabel('Strength', { exact: true }),
  ).toHaveValue('17');
  await expect(page.locator('[data-name-edit]')).toBeVisible();
});

test('the sticky bar shows the name, the numbers and the same switch once the header has scrolled away', async ({
  world,
  as,
}) => {
  const strength = await world.defineStat('abilities', 'strength', 'int');
  await world.setStat(world.pia.character.entity_id, strength.id, 17);
  for (let i = 0; i < 6; i++) {
    await world.note(world.pia.character.entity_id, `Note ${i}`, 'Text '.repeat(80), true);
  }
  const page = await as(world.gm);
  await page.setViewportSize({ width: 1280, height: 600 });
  await page.goto(url(world, world.pia.character.entity_id));

  const bar = page.locator('[data-sticky]');
  await expect(page.getByRole('heading', { name: 'Note 5' })).toBeVisible();
  await expect(bar).toBeHidden();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(bar).toBeVisible();
  await expect(bar.locator('[data-sticky-name]')).toHaveText('Ashfang');
  await expect(bar.locator('[data-vitals]')).toContainText('Strength 17');

  await bar.getByText('Play', { exact: true }).click();
  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', 'play');
  await expect(page.locator('[data-live]')).toHaveText('Play mode');
});

test('Edit is offered to a GM and to the player of the being, and to nobody else', async ({
  world,
  as,
}) => {
  const edit = (page: import('@playwright/test').Page) =>
    page.locator('[data-sheet-head] [data-mode-switch] input[value="edit"]');
  const gm = await as(world.gm);
  await gm.goto(url(world, world.pia.character.entity_id));
  await expect(edit(gm)).toBeEnabled();

  const mine = await as(world.pia);
  await mine.goto(url(world, world.pia.character.entity_id));
  await expect(edit(mine)).toBeEnabled();

  const other = await as(world.pia);
  await other.goto(url(world, world.oskar.character.entity_id));
  await expect(edit(other)).toBeDisabled();
  await expect(other.locator('[data-sheet-head] [data-mode-switch] label').last()).toHaveAttribute(
    'title',
    /edit/i,
  );
});
