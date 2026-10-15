import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import { enterMode } from './support/modes.ts';

test('the being group and valued stats are the same in every mode and both layouts', async ({
  world,
  as,
}) => {
  const hp = await world.defineStat('vitals', 'hit_points', 'int');
  await world.defineStat('vitals', 'speed', 'int');
  const damage = await world.defineStat('weapons', 'damage', 'int');
  await world.defineStat('weapons', 'reach', 'int');
  const being = world.pia.character.entity_id;
  await world.setStat(being, damage.id, 0);
  await ok(
    world.gm.api.PATCH('/tenants/{tenant_id}', {
      params: { path: { tenant_id: world.tenantId } },
      body: { being_stat_group_id: hp.stat_group_id },
    }),
  );

  // A player reads the tenant selection too; a membership is not needed.
  const page = await as(world.pia);
  await page.goto(`/being/?tenant=${world.tenantId}&id=${being}`);
  for (const layout of ['Sheet', 'Datasheet'] as const) {
    await page
      .locator('[data-sheet-head] [data-layout-switch]')
      .getByText(layout, { exact: true })
      .click();
    const band = page.locator(layout === 'Sheet' ? '[data-stat-band]' : '[data-ds-lines]');
    for (const mode of ['Read', 'Play', 'Edit'] as const) {
      await enterMode(page, mode);
      await expect(band.locator('[data-stat="hit_points"]')).toBeVisible();
      await expect(band.locator('[data-stat="speed"]')).toBeVisible();
      await expect(band.locator('[data-stat="damage"]')).toBeVisible();
      await expect(band.locator('[data-stat="reach"]')).toHaveCount(0);
      if (mode === 'Read') {
        await expect(band.locator('[data-stat="hit_points"] .stat-value')).toHaveText('—');
        await expect(band.locator('[data-stat="damage"] .stat-value')).toHaveText('0');
      }
    }
  }
  const band = page.locator('[data-ds-lines]');
  await band.getByRole('button', { name: 'Use inherited Damage' }).click();
  await expect(band.locator('[data-stat="damage"]')).toHaveCount(0);
  await expect(band.getByLabel('Hit points', { exact: true })).toBeVisible();
});

test('without a being group, only valued stats appear even in Edit', async ({ world, as }) => {
  const hp = await world.defineStat('vitals', 'hit_points', 'int');
  await world.defineStat('weapons', 'reach', 'int');
  const being = world.pia.character.entity_id;
  await world.setStat(being, hp.id, 0);
  const page = await as(world.pia);
  await page.goto(`/being/?tenant=${world.tenantId}&id=${being}`);
  await enterMode(page, 'Edit');
  const band = page.locator('[data-stat-band]');
  await expect(band.getByLabel('Hit points', { exact: true })).toHaveValue('0');
  await expect(band.locator('[data-stat="reach"]')).toHaveCount(0);
  await band.getByRole('button', { name: 'Use inherited Hit points' }).click();
  await expect(band.locator('[data-stat="hit_points"]')).toHaveCount(0);
});
