import { expect, test } from './support/fixtures.ts';

const url = (world: { tenantId: string }, id: string) =>
  `/being/?tenant=${world.tenantId}&id=${id}`;

const datasheet = (page: import('@playwright/test').Page) => page.locator('[data-datasheet]');

async function layout(page: import('@playwright/test').Page, name: 'Sheet' | 'Datasheet') {
  await expect(page.locator('[data-title]')).not.toBeEmpty();
  await page
    .locator('[data-sheet-head] [data-layout-switch]')
    .getByText(name, { exact: true })
    .click();
  await expect(page.locator('[data-being-page]')).toHaveAttribute(
    'data-layout',
    name.toLowerCase(),
  );
}

test('the datasheet shows the stat lines, the equipped weapons as a table and the abilities', async ({
  world,
  as,
}) => {
  const being = world.pia.character.entity_id;
  const strength = await world.defineStat('abilities', 'strength', 'int');
  const reach = await world.defineStat('weapons', 'reach', 'int', { unit: 'ft' });
  const damage = await world.defineStat('weapons', 'damage', 'int');
  await world.setStat(being, strength.id, 17);
  await world.equip(world.pia.character, 'Longsword', [
    [reach.id, 5],
    [damage.id, 8],
  ]);
  await world.equip(world.pia.character, 'Dagger', [[damage.id, 4]]);
  await world.note(being, 'Second wind', 'Heals a little.', true, 'ability');
  await world.note(being, 'Backstory', 'Raised by wolves.', true);
  await world.configureSheet(reach.stat_group_id, 'ability');

  const page = await as(world.gm);
  await page.goto(url(world, being));
  await layout(page, 'Datasheet');

  const sheet = datasheet(page);
  await expect(page.locator('.sheet-layout')).toBeHidden();
  await expect(sheet.locator('.ds-line h3')).toHaveText(['abilities']);
  await expect(sheet.locator('.ds-cell[data-stat="strength"] .stat-value')).toHaveText('17');

  const table = sheet.locator('.ds-table');
  await expect(table.locator('th')).toHaveText(['Weapon', 'Reach', 'Damage']);
  await expect(table.locator('tbody tr')).toHaveText([/Dagger\s*—\s*4/, /Longsword\s*5 ft\s*8/]);

  const notes = sheet.locator('.ds-note');
  await expect(notes.locator('strong')).toHaveText(['Second wind', 'Backstory']);
  await expect(sheet.getByText('Raised by wolves.')).toBeVisible();
});

test('a library that has not said where weapons are gets what the being carries', async ({
  world,
  as,
}) => {
  const being = world.pia.character.entity_id;
  await world.carry(world.pia.character, 'Torch');
  const page = await as(world.gm);
  await page.goto(url(world, being));
  await layout(page, 'Datasheet');

  const table = datasheet(page).locator('.ds-table');
  await expect(table.locator('th')).toHaveText(['Item', 'Qty']);
  await expect(table.locator('tbody tr')).toHaveText([/Torch\s*1/]);
  await expect(datasheet(page).getByText('No stats')).toBeVisible();
});

test('a number changes in the datasheet in Play, as on the sheet', async ({ world, as }) => {
  const being = world.pia.character.entity_id;
  const hp = await world.defineStat('vitals', 'hit_points', 'int', { adjustable_in_play: true });
  await world.setStat(being, hp.id, 9);
  const page = await as(world.pia);
  await page.goto(url(world, being));
  await layout(page, 'Datasheet');
  await page
    .locator('[data-sheet-head] [data-mode-switch]')
    .getByText('Play', { exact: true })
    .click();

  const cell = datasheet(page).locator('.ds-cell[data-stat="hit_points"]');
  await cell.getByRole('button', { name: 'Lower Hit points by 1' }).click();
  await expect(cell.locator('.stat-value')).toContainText('8');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(cell.locator('.stat-value')).toContainText('9');
});

test('another player’s datasheet has no weapons, and a note says who wrote it', async ({
  world,
  as,
}) => {
  const being = world.pia.character.entity_id;
  const damage = await world.defineStat('weapons', 'damage', 'int');
  await world.equip(world.pia.character, 'Longsword', [[damage.id, 8]]);
  await world.note(being, 'For all', 'Known to everyone.', true);
  await world.configureSheet(damage.stat_group_id, null);

  const mine = await as(world.pia);
  await mine.goto(url(world, being));
  await layout(mine, 'Datasheet');
  await expect(datasheet(mine).locator('.ds-table tbody tr')).toHaveCount(1);

  const other = await as(world.oskar);
  await other.goto(url(world, being));
  await layout(other, 'Datasheet');
  await expect(datasheet(other).getByText('Known to everyone.')).toBeVisible();
  await expect(datasheet(other).locator('[data-ds-weapons]')).toBeHidden();
  // Back to the sheet: the note shows its author.
  await layout(other, 'Sheet');
  await expect(other.locator('[data-being-notes] [data-author]')).toHaveText(/\S/);
});
