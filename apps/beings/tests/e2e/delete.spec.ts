import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';

// The shell's confirmation: the name is typed before the button works.
async function confirmDelete(page: import('@playwright/test').Page, name: string) {
  const dialog = page.getByRole('dialog', { name: `Delete ${name}?` });

  await dialog.getByLabel(`Type “${name}” to confirm`).fill(name);
  await dialog.getByRole('button', { name: 'Delete being' }).click();
}

const url = (tenantId: string, entityId: string) => `/being/?tenant=${tenantId}&id=${entityId}`;

test('deletion is confirmed, settles inventory and returns to the list', async ({ world, as }) => {
  const being = await world.npc('Departing Goblin');
  const removed = await world.equip(being, 'Carried sword');
  const kept = await world.carry(being, 'Stored shield');
  await world.slug(being.entity_id, 'departing-goblin');
  await world.note(being.entity_id, 'Last note', 'Remember this goblin.');
  const page = await as(world.gm);
  await page.goto(url(world.tenantId, being.entity_id));
  const remove = page.locator('[data-delete-being]').getByRole('button', { name: 'Delete being' });
  await expect(remove).toBeHidden();
  await expect(remove).toBeVisible();

  await remove.click();
  const asking = page.getByRole('dialog', { name: 'Delete Departing Goblin?' });
  await expect(asking).toContainText("can't be undone");
  await expect(asking).toContainText('owns and carries');
  // The button does nothing until the name is typed.
  await expect(asking.getByRole('button', { name: 'Delete being' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
  await asking.getByRole('button', { name: 'Cancel' }).click();
  await expect(asking).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Departing Goblin', level: 1 })).toBeVisible();
  await remove.click();
  await confirmDelete(page, 'Departing Goblin');
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
  await page.locator('[data-delete-being]').getByRole('button', { name: 'Delete being' }).click();
  await confirmDelete(page, 'Ashfang');
  await expect(page).toHaveURL(`/beings/?tenant=${world.tenantId}`);
});

test('another player has no deletion control', async ({ world, as }) => {
  const page = await as(world.oskar);
  await page.goto(url(world.tenantId, world.pia.character.entity_id));
  await expect(page.getByRole('heading', { name: 'Ashfang', level: 1 })).toBeVisible();
  await expect(
    page.locator('[data-delete-being]').getByRole('button', { name: 'Delete being' }),
  ).toBeHidden();
});

test('an API refusal stays on the page and makes retry possible', async ({ world, as }) => {
  const being = await world.npc('Staying Goblin');
  const page = await as(world.gm);
  await page.goto(url(world.tenantId, being.entity_id));
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
  const remove = page.locator('[data-delete-being]').getByRole('button', { name: 'Delete being' });
  await remove.click();
  await confirmDelete(page, 'Staying Goblin');
  await expect(page.locator('[data-delete-being] [data-status]')).toContainText(
    'This being changed',
  );
  await expect(remove).toBeEnabled();
  await expect(page.getByRole('heading', { name: 'Staying Goblin', level: 1 })).toBeVisible();
});
