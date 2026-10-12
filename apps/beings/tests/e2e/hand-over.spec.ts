import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';

test('a GM creates a being, which starts as an NPC, and hands it over to a player', async ({
  world,
  as,
}) => {
  const page = await as(world.gm);
  await page.goto(`/beings/?tenant=${world.tenantId}`);

  await page.getByLabel('Name', { exact: true }).fill('Thorn');
  await page.getByRole('button', { name: 'Create being' }).click();
  await expect(page.getByRole('heading', { name: 'Thorn', level: 1 })).toBeVisible();
  await expect(page.locator('[data-kind]')).toHaveText('NPC');

  const handOver = page.locator('[data-hand-over]');
  await handOver.getByLabel('Campaign').selectOption({ label: 'The Sunken Crown' });
  const pia = handOver.locator('li', { hasText: 'Pia' });
  await expect(pia).toBeVisible();
  await expect(handOver.locator('li', { hasText: 'Oskar' })).toBeVisible();
  await pia.getByRole('button', { name: 'Hand over' }).click();

  await expect(page.locator('[data-kind]')).toHaveText('Character');
  const owner = page.locator('[data-people] li', { hasText: 'Pia' });
  await expect(owner).toContainText('Owner');

  // On the API's own record: Pia owns it now.
  const thorn = new URL(page.url()).searchParams.get('id');
  const slug = new URL(page.url()).searchParams.get('slug');
  const found = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/beings', {
      params: { path: { tenant_id: world.tenantId }, query: { q: 'Thorn' } },
    }),
  );
  const id = thorn ?? found.items[0]?.entity_id ?? '';
  expect(slug ?? id).toBeTruthy();
  const character = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/characters/{character_id}', {
      params: { path: { tenant_id: world.tenantId, character_id: id } },
    }),
  );
  expect(character.owner_player_id).toBe(world.pia.playerId);
});

test('a player makes a character of their own, which they own from the start', async ({
  world,
  as,
}) => {
  const page = await as(world.pia);
  await page.goto(`/beings/?tenant=${world.tenantId}`);

  const form = page.locator('[data-own-form]');
  await expect(form.getByLabel('Where you play')).toContainText('The Sunken Crown');
  await form.getByLabel('Character name').fill('Wren');
  await form.getByRole('button', { name: 'Create character' }).click();

  await expect(page.getByRole('heading', { name: 'Wren', level: 1 })).toBeVisible();
  await expect(page.locator('[data-kind]')).toHaveText('Character');
  await expect(page.locator('[data-people] li', { hasText: 'Pia' })).toContainText('Owner');

  const found = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/beings', {
      params: { path: { tenant_id: world.tenantId }, query: { q: 'Wren' } },
    }),
  );
  const character = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/characters/{character_id}', {
      params: {
        path: { tenant_id: world.tenantId, character_id: found.items[0]?.entity_id ?? '' },
      },
    }),
  );
  expect(character.owner_player_id).toBe(world.pia.playerId);
});

test('a player is offered no form for an NPC and no hand over', async ({ world, as }) => {
  const page = await as(world.pia);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create being' })).toBeHidden();
});
