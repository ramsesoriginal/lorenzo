import { expect, test } from './support/fixtures.ts';
import { editDetails, enterMode, pageMenu } from './support/modes.ts';

const url = (world: { tenantId: string }, id: string) =>
  `/being/?tenant=${world.tenantId}&id=${id}`;

// The sections of a being's sheet, top to bottom, as the page draws them.
const order = (page: import('@playwright/test').Page) =>
  page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('[data-sheet-main] > [data-section]')]
      .sort((a, b) => Number(a.style.order) - Number(b.style.order))
      .map((section) => section.dataset.section),
  );

test('Read puts the prose first and Play the numbers first, and there is no Edit mode', async ({
  world,
  as,
}) => {
  const strength = await world.defineStat('abilities', 'strength', 'int');
  await world.setStat(world.pia.character.entity_id, strength.id, 17);
  const page = await as(world.gm);
  await page.goto(url(world, world.pia.character.entity_id));

  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', 'read');
  expect(await order(page)).toEqual(['about', 'notes', 'stats', 'inventory']);
  await expect(page.locator('[data-band] [data-mode-switch] label')).toHaveText(['Read', 'Play']);

  await enterMode(page, 'Play');
  expect(await order(page)).toEqual(['stats', 'inventory', 'notes', 'about']);
  await expect(page.locator('[data-stat-band]').getByRole('textbox')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Edit Strength' })).toHaveCount(0);
  await expect(pageMenu(page)).toBeHidden();

  // In Read a number is edited where it is, and saves on its own.
  await enterMode(page, 'Read');
  await page.getByRole('button', { name: 'Edit Strength', exact: true }).click();
  const field = page.locator('[data-stat-band]').getByLabel('Strength', { exact: true });
  await expect(field).toHaveValue('17');
  await field.fill('18');
  await field.press('Enter');
  await expect(page.locator('[data-save-status]')).toHaveText('Saved.');
  await page.getByRole('button', { name: 'Done editing Strength' }).click();
  await expect(page.locator('[data-stat="strength"] .stat-value')).toHaveText('18');
  await expect(page.locator('[data-stat-band]').getByRole('textbox')).toHaveCount(0);
});

test('the band says what each mode is for, and the details open only on request', async ({
  world,
  as,
}) => {
  const page = await as(world.gm);
  await page.goto(url(world, world.pia.character.entity_id));
  const line = page.locator('[data-band] [data-mode-line]');

  await expect(line).toHaveText('Reading. Edit a section where it is.');
  await expect(page.locator('[data-name-edit]')).toBeHidden();
  await editDetails(page);
  await expect(page.locator('[data-name-edit]')).toBeVisible();
  await page.getByRole('button', { name: 'Done editing details' }).click();
  await expect(page.locator('[data-name-edit]')).toBeHidden();

  await enterMode(page, 'Play');
  await expect(line).toHaveText('At the table. Numbers first; every change can be undone.');
});

test('a being opens in the mode last used on it, for whoever may change it', async ({
  world,
  as,
}) => {
  const target = world.pia.character.entity_id;
  const page = await as(world.pia);
  await page.goto(url(world, target));
  // Once the page knows who may change the being, the mode is kept for it.
  await expect(pageMenu(page)).toBeVisible();
  await enterMode(page, 'Play');

  await page.reload();
  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', 'play');
  await expect(page.locator('[data-band] [data-mode-switch] input[value="play"]')).toBeChecked();

  // Another being of the same person has its own memory.
  await page.goto(url(world, world.oskar.character.entity_id));
  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', 'read');
});

test('the band stays in view and shrinks to show the name once the header has scrolled away', async ({
  world,
  as,
}) => {
  const strength = await world.defineStat('abilities', 'strength', 'int', { pin: true });
  await world.setStat(world.pia.character.entity_id, strength.id, 17);
  for (let i = 0; i < 6; i++) {
    await world.note(world.pia.character.entity_id, `Note ${i}`, 'Text '.repeat(80), true);
  }
  const page = await as(world.gm);
  await page.setViewportSize({ width: 1280, height: 600 });
  await page.goto(url(world, world.pia.character.entity_id));

  const bar = page.locator('[data-band]');
  await expect(page.getByRole('heading', { name: 'Note 5' })).toBeVisible();
  await expect(bar).toBeVisible();
  await expect(bar.locator('[data-pins]')).toContainText('Strength');
  await expect(bar.locator('[data-pins]')).toContainText('17');
  await expect(bar.locator('[data-sticky-name]')).toBeHidden();
  await expect(bar).not.toHaveClass(/is-compact/);

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(bar).toHaveClass(/is-compact/);
  await expect(bar).toBeVisible();
  await expect(bar.locator('[data-sticky-name]')).toHaveText('Ashfang');
  await expect(bar.locator('[data-pins]')).toContainText('17');

  await bar.getByText('Play', { exact: true }).click();
  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', 'play');
  await expect(page.locator('[data-live]')).toHaveText('Play mode');
});

test('editing is offered to a GM and to the player of the being, and to nobody else', async ({
  world,
  as,
}) => {
  const edit = pageMenu;
  const gm = await as(world.gm);
  await gm.goto(url(world, world.pia.character.entity_id));
  await expect(edit(gm)).toBeVisible();

  const mine = await as(world.pia);
  await mine.goto(url(world, world.pia.character.entity_id));
  await expect(edit(mine)).toBeVisible();

  const other = await as(world.pia);
  await other.goto(url(world, world.oskar.character.entity_id));
  await expect(other.getByRole('heading', { name: 'Brisk', level: 1 })).toBeVisible();
  await expect(edit(other)).toBeHidden();
});
