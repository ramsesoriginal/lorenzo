import { expect, test } from './support/fixtures.ts';
import { enterMode } from './support/modes.ts';

const url = (world: { tenantId: string }, id: string) =>
  `/being/?tenant=${world.tenantId}&id=${id}`;

// What the library sets for a number a table changes: a maximum to show, and a floor to stop at.
async function hitPoints(
  world: Awaited<ReturnType<typeof import('./support/world.ts').buildWorld>>,
) {
  const max = await world.defineStat('vitals', 'hit_points_max', 'int');
  const zero = await world.defineStat('vitals', 'zero', 'int');
  const hp = await world.defineStat('vitals', 'hit_points', 'int', {
    adjustable_in_play: true,
    pin: true,
    unit: 'hp',
    max_hint_id: max.id,
    min_hint_id: zero.id,
  });
  const being = world.pia.character.entity_id;

  await world.setStat(being, max.id, 9);
  await world.setStat(being, zero.id, 0);
  await world.setStat(being, hp.id, 9);

  return { being, hp };
}

test('in Play a number steps, takes away an amount and stops at its floor, each change undoable', async ({
  world,
  as,
}) => {
  const { being } = await hitPoints(world);
  const page = await as(world.pia);
  await page.goto(url(world, being));
  await enterMode(page, 'Play');

  const tile = page.locator('[data-stat="hit_points"]');
  await expect(tile).toContainText('of 9');
  await expect(tile.locator('.stat-value')).toContainText('9');

  await tile.getByRole('button', { name: 'Lower Hit points by 1' }).click();
  await expect(tile.locator('.stat-value')).toContainText('8');
  await expect(page.locator('[data-undo-bar]')).toContainText('Hit points 9 → 8');
  await expect(page.locator('[data-live]')).toHaveText('Hit points 9 → 8');

  // The adjuster says it as the table does: "take away 20", and the floor holds it at zero.
  await tile.getByRole('button', { name: /Change Hit points/ }).click();
  await page.getByLabel('Amount').fill('20');
  await page.getByRole('button', { name: 'Take away' }).click();
  await expect(tile.locator('.stat-value')).toContainText('0');
  await expect(page.locator('[data-undo-bar]')).toContainText('Hit points 8 → 0');
  await expect(tile.locator('.stat-delta')).toHaveText('−8');

  // It is what the API says: a reload shows it, and so does Undo, on the button and on Ctrl+Z.
  await page.reload();
  await enterMode(page, 'Play');
  await expect(tile.locator('.stat-value')).toContainText('0');

  await tile.getByRole('button', { name: 'Raise Hit points by 1' }).click();
  await expect(tile.locator('.stat-value')).toContainText('1');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(tile.locator('.stat-value')).toContainText('0');
  await expect(page.locator('[data-live]')).toHaveText('Undone: Hit points 0 → 1');
});

test('Ctrl+Z takes back the last change in Play', async ({ world, as }) => {
  const { being } = await hitPoints(world);
  const page = await as(world.pia);
  await page.goto(url(world, being));
  await enterMode(page, 'Play');

  const tile = page.locator('[data-stat="hit_points"]');
  await tile.getByRole('button', { name: 'Lower Hit points by 1' }).click();
  await expect(tile.locator('.stat-value')).toContainText('8');
  await page.locator('body').press('Control+z');
  await expect(tile.locator('.stat-value')).toContainText('9');
});

test('the numbers a library pins stay in the sticky bar', async ({ world, as }) => {
  const { being } = await hitPoints(world);
  for (let i = 0; i < 6; i++) {
    await world.note(being, `Note ${i}`, 'Text '.repeat(80), true);
  }
  const page = await as(world.pia);
  await page.setViewportSize({ width: 1280, height: 600 });
  await page.goto(url(world, being));
  await expect(page.getByRole('heading', { name: 'Note 5' })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

  await expect(page.locator('[data-vitals]')).toHaveText(/Hit points\s*9 hp/);
});

test('someone who may not edit a being gets no steppers in Play', async ({ world, as }) => {
  const { being } = await hitPoints(world);
  const page = await as(world.oskar);
  await page.goto(url(world, being));
  await enterMode(page, 'Play');

  await expect(page.locator('[data-stat="hit_points"]')).toContainText('9');
  await expect(page.getByRole('button', { name: 'Lower Hit points by 1' })).toHaveCount(0);
});

test('an adjustable tag is a toggle in Play, and can be taken back', async ({ world, as }) => {
  await world.defineStat('tags', 'prone', 'bool', { adjustable_in_play: true });
  await world.defineStat('tags', 'is_undead', 'bool');
  const page = await as(world.pia);
  await page.goto(url(world, world.pia.character.entity_id));
  await enterMode(page, 'Play');

  const prone = page.locator('[data-tag-chips]').getByRole('button', { name: 'Prone' });
  await expect(prone).toHaveAttribute('aria-pressed', 'false');
  // A tag the library does not call adjustable is not offered.
  await expect(page.locator('[data-tag-chips]').getByText('Undead')).toHaveCount(0);

  await prone.click();
  await expect(prone).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('[data-live]')).toHaveText('Prone on');

  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(prone).toHaveAttribute('aria-pressed', 'false');
});

test('a calculated number says so and shows how it came to be', async ({ world, as }) => {
  const dex = await world.defineStat('abilities', 'dexterity', 'int');
  const armour = await world.defineStat('abilities', 'armour_class', 'int');
  const being = world.pia.character.entity_id;
  await world.setStat(being, dex.id, 14);
  await world.formula(being, armour.id, dex.id, '1', '1');
  const page = await as(world.gm);
  await page.goto(url(world, being));

  const tile = page.locator('[data-stat="armour_class"]');
  await expect(tile.locator('.stat-value')).toContainText('15');
  await tile.getByText('Calculated').click();
  const panel = tile.locator('.why-panel');
  await expect(panel).toContainText('Dexterity × 1 + 1');
  await expect(panel).toContainText('Dexterity');
  await expect(panel).toContainText('14');
  await expect(panel.locator('dd').last()).toHaveText('15');
});

test('a value shown with its sign and the stat that resolves it sit beside the number', async ({
  world,
  as,
}) => {
  const modifier = await world.defineStat('abilities', 'strength_modifier', 'int', {
    signed: true,
  });
  const strength = await world.defineStat('abilities', 'strength', 'int', {
    resolved_hint_id: modifier.id,
  });
  const being = world.pia.character.entity_id;
  await world.setStat(being, strength.id, 16);
  await world.setStat(being, modifier.id, 3);
  const page = await as(world.gm);
  await page.goto(url(world, being));

  await expect(page.locator('[data-stat="strength"] .stat-sub')).toHaveText('+3');
  await expect(page.locator('[data-stat="strength_modifier"] .stat-value')).toHaveText('+3');
});
