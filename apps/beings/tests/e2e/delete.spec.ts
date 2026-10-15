import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import { enterMode } from './support/modes.ts';

const url = (tenantId: string, entityId: string) => `/being/?tenant=${tenantId}&id=${entityId}`;

test('deletion is confirmed, settles inventory and returns to the list', async ({ world, as }) => {
  const being = await world.npc('Departing Goblin');
  const removed = await world.equip(being, 'Carried sword');
  const kept = await world.carry(being, 'Stored shield');
  await world.slug(being.entity_id, 'departing-goblin');
  await world.note(being.entity_id, 'Last note', 'Remember this goblin.');
  const page = await as(world.gm);
  await page.goto(url(world.tenantId, being.entity_id));
  const remove = page.getByRole('button', { name: 'Delete being', exact: true });
  await expect(remove).toBeHidden();
  await enterMode(page, 'Edit');
  await expect(remove).toBeVisible();

  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain('Departing Goblin');
    expect(dialog.message()).toContain("can't be undone");
    expect(dialog.message()).toContain('owns and carries');
    await dialog.dismiss();
  });
  await remove.click();
  await expect(page.getByRole('heading', { name: 'Departing Goblin', level: 1 })).toBeVisible();
  page.once('dialog', (dialog) => dialog.accept());
  await remove.click();
  await expect(page).toHaveURL(`/beings/?tenant=${world.tenantId}`);

  const path = { tenant_id: world.tenantId, entity_id: being.entity_id };
  expect(
    (
      await world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path },
      })
    ).response.status,
  ).toBe(404);
  expect(
    (
      await world.gm.api.GET('/tenants/{tenant_id}/item-instances/{entity_id}', {
        params: { path: { ...path, entity_id: removed } },
      })
    ).response.status,
  ).toBe(404);
  const surviving = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/item-instances/{entity_id}', {
      params: { path: { ...path, entity_id: kept } },
    }),
  );
  expect(surviving.owner_entity_id).toBeNull();
  expect(surviving.container_entity_id).toBeNull();
});

test('a player can delete their own being', async ({ world, as }) => {
  const page = await as(world.pia);
  await page.goto(url(world.tenantId, world.pia.character.entity_id));
  await enterMode(page, 'Edit');
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Delete being', exact: true }).click();
  await expect(page).toHaveURL(`/beings/?tenant=${world.tenantId}`);
});

test('another player has no deletion control', async ({ world, as }) => {
  const page = await as(world.oskar);
  await page.goto(url(world.tenantId, world.pia.character.entity_id));
  await expect(page.getByRole('heading', { name: 'Ashfang', level: 1 })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Delete being', exact: true })).toBeHidden();
});

test('an API refusal stays on the page and makes retry possible', async ({ world, as }) => {
  const being = await world.npc('Staying Goblin');
  const page = await as(world.gm);
  await page.goto(url(world.tenantId, being.entity_id));
  await enterMode(page, 'Edit');
  await page.route(`**/tenants/${world.tenantId}/beings/${being.entity_id}`, (route) =>
    route.fulfill({
      status: 412,
      contentType: 'application/problem+json',
      body: JSON.stringify({
        title: 'Precondition failed',
        status: 412,
        detail: 'This being changed. Read it again before deleting.',
      }),
    }),
  );
  page.once('dialog', (dialog) => dialog.accept());
  const remove = page.getByRole('button', { name: 'Delete being', exact: true });
  await remove.click();
  await expect(page.locator('[data-delete-being] [data-status]')).toContainText(
    'This being changed',
  );
  await expect(remove).toBeEnabled();
  await expect(page.getByRole('heading', { name: 'Staying Goblin', level: 1 })).toBeVisible();
});
