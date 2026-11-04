import { randomUUID } from 'node:crypto';
import { ok } from '../../../beings/tests/e2e/support/api.ts';
import { expect, test } from '../../../beings/tests/e2e/support/fixtures.ts';

// ADR 0385: a stat and one of its values are renamed in place, and the entries that hold the
// value follow (the server rewrites every stored copy, a comparison formula's result included).
test('a stat and an enum value are renamed, and what held the value follows', async ({
  world,
  as,
}) => {
  const api = world.gm.api;
  const repository = await ok(
    api.POST('/tenants', { body: { name: `Rarities ${randomUUID()}`, kind: 'repository' } }),
  );
  const path = { tenant_id: repository.id };
  const group = await ok(
    api.POST('/tenants/{tenant_id}/stat-groups', {
      params: { path },
      body: { name: 'Looks', priority: 0, mandatory: false },
    }),
  );
  const rarity = await ok(
    api.POST('/tenants/{tenant_id}/stat-definitions', {
      params: { path },
      body: {
        name: 'Rarity',
        stat_group_id: group.id,
        value_type: 'enum',
        enum_values: ['common', 'rare'],
        adjustable_in_play: false,
        pin: false,
        signed: false,
      },
    }),
  );
  const sword = await ok(
    api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Sword', kinds: ['item'], parents: [] },
    }),
  );
  await ok(
    api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: { path: { ...path, entity_id: sword.id, stat_definition_id: rarity.id } },
      body: { value: 'rare', acquire_group: true },
    }),
  );

  const page = await as(world.gm);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.getByRole('button', { name: 'A to Z', exact: true }).click();
  await page.locator(`[data-entry="${sword.id}"]`).first().click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Sword');
  // Read the entry, so that the mirror holds the old value.
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');

  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('Open Vocabulary');
  await page.keyboard.press('Enter');
  const pane = page.locator('.pane-vocabulary');
  await pane.getByRole('button', { name: 'Rename the value rare' }).click();
  await pane.getByLabel('New name of rare').fill('scarce');
  await pane.getByLabel('New name of rare').press('Enter');
  await expect(pane.locator('.vocab-stat', { hasText: 'Rarity' })).toContainText('common · scarce');
  await pane.getByRole('button', { name: 'Rename Rarity' }).click();
  await pane.getByLabel('New name of Rarity').fill('Scarcity');
  await pane.getByLabel('New name of Rarity').press('Enter');
  await expect(pane.locator('.vocab-stat', { hasText: 'Scarcity' })).toBeVisible();

  const held = await ok(
    api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { ...path, entity_id: sword.id } },
    }),
  );
  expect(held.stats.map((s) => [s.name, s.value])).toEqual([['Scarcity', 'scarce']]);

  // A name that is taken is said in the API's words and changes nothing: the line stays open with what was typed.
  await pane.getByLabel('Name of the new stat').fill('Reach');
  await pane.getByRole('button', { name: 'Make the stat' }).click();
  await pane.getByRole('button', { name: 'Rename Reach' }).click();
  await pane.getByLabel('New name of Reach').fill('Scarcity');
  await pane.getByLabel('New name of Reach').press('Enter');
  await expect(pane.locator('.formula-note')).toContainText('already');
  await expect(pane.getByLabel('New name of Reach')).toHaveValue('Scarcity');
});
