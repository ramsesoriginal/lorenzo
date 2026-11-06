import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';

test('a being with relationships shows them drawn around it and in words', async ({
  world,
  as,
}) => {
  const goblin = await world.npc('Goblin Chief');
  const hold = await ok(
    world.gm.api.POST('/tenants/{tenant_id}/locations', {
      params: { path: { tenant_id: world.tenantId } },
      body: { name: 'Ash Hold', is_public: true },
    }),
  );
  await ok(
    world.gm.api.POST('/tenants/{tenant_id}/relationships', {
      params: { path: { tenant_id: world.tenantId } },
      body: {
        name: 'Goblin Chief rules Ash Hold',
        end_a: goblin.entity_id,
        end_b: hold.id,
        one_way: true,
        is_public: true,
      },
    }),
  );
  const page = await as(world.gm);
  await page.goto(`/being/?tenant=${world.tenantId}&id=${goblin.entity_id}`);

  const section = page.locator('[data-being-relationships]');
  await expect(section).toBeVisible();
  await expect(section.getByRole('heading', { name: 'Relationships', level: 2 })).toBeVisible();
  const drawing = section.getByRole('group', { name: 'Relationships of Goblin Chief' });
  await expect(drawing.getByRole('button', { name: 'Ash Hold' })).toBeVisible();
  await expect(drawing.getByRole('button', { name: 'Goblin Chief' })).toBeVisible();
  await expect(
    section.getByText('Goblin Chief rules Ash Hold: From Goblin Chief to Ash Hold.'),
  ).toBeVisible();
});

test('a being with no relationship you may see shows no section at all', async ({ world, as }) => {
  const lonely = await world.npc('Lonely Ogre');
  const vault = await ok(
    world.gm.api.POST('/tenants/{tenant_id}/locations', {
      params: { path: { tenant_id: world.tenantId } },
      body: { name: 'The sealed vault', is_public: false },
    }),
  );
  // A relationship whose other end the reader cannot see is not shown to them.
  await ok(
    world.gm.api.POST('/tenants/{tenant_id}/relationships', {
      params: { path: { tenant_id: world.tenantId } },
      body: {
        name: 'Ogre guards the vault',
        end_a: lonely.entity_id,
        end_b: vault.id,
        one_way: true,
        is_public: true,
      },
    }),
  );
  const page = await as(world.pia);
  await page.goto(`/being/?tenant=${world.tenantId}&id=${lonely.entity_id}`);
  await expect(page.getByRole('heading', { name: 'Lonely Ogre', level: 1 })).toBeVisible();
  await expect(page.locator('[data-being-relationships]')).toBeHidden();
  await expect(page.getByText('sealed vault')).toHaveCount(0);
});
