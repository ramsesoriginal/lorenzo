import { randomUUID } from 'node:crypto';
import { ok } from '../../../beings/tests/e2e/support/api.ts';
import { expect, test } from '../../../beings/tests/e2e/support/fixtures.ts';

// ADR 0386: deleting an entry says how many libraries have copied it, and goes through.
test('an entry is deleted with the number of libraries that copied it said first', async ({
  world,
  as,
}) => {
  const api = world.gm.api;
  const repository = await ok(
    api.POST('/tenants', { body: { name: `Armoury ${randomUUID()}`, kind: 'repository' } }),
  );
  const path = { tenant_id: repository.id };
  const kept = await ok(
    api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Longsword', kinds: ['item'], parents: [] },
    }),
  );
  const gone = await ok(
    api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Dagger', kinds: ['item'], parents: [] },
    }),
  );
  const library = await ok(
    api.POST('/tenants', { body: { name: `Table ${randomUUID()}`, kind: 'play' } }),
  );
  await ok(
    api.PUT('/tenants/{tenant_id}/subscribers/{subscriber_tenant_id}', {
      params: { path: { ...path, subscriber_tenant_id: library.id } },
    }),
  );
  await ok(api.PUT('/tenants/{tenant_id}/published', { params: { path } }));
  await ok(
    api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: library.id, repository_id: repository.id } },
      body: {},
    }),
  );
  // One more entry the library has not seen: nobody holds it.
  const fresh = await ok(
    api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Pebble', kinds: ['item'], parents: [] },
    }),
  );

  const page = await as(world.gm);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.getByRole('button', { name: 'A to Z', exact: true }).click();

  await page.locator(`[data-entry="${gone.id}"]`).first().click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Dagger');
  await page.getByRole('button', { name: 'Delete Dagger' }).click();
  const ask = page.getByRole('group', { name: 'Delete Dagger' });
  await expect(ask).toContainText('1 library has copied this. It will see it as removed upstream.');
  await ask.getByRole('button', { name: 'Keep it' }).click();
  await expect(ask).toHaveCount(0);

  await page.getByRole('button', { name: 'Delete Dagger' }).click();
  await ask.getByRole('button', { name: 'Delete it' }).click();
  await expect(page.locator(`[data-entry="${gone.id}"]`)).toHaveCount(0);
  const after = await api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path: { ...path, entity_id: gone.id } },
  });
  expect(after.response.status).toBe(404);
  const still = await api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path: { ...path, entity_id: kept.id } },
  });
  expect(still.response.status).toBe(200);

  // The library keeps its own copy, and the repository's log says how many held it.
  const copies = await ok(
    api.GET('/tenants/{tenant_id}/entities', { params: { path: { tenant_id: library.id } } }),
  );
  expect(copies.items.map((e) => e.name).sort()).toEqual(['Dagger', 'Longsword']);

  await page.locator(`[data-entry="${fresh.id}"]`).first().click();
  await page.getByRole('button', { name: 'Delete Pebble' }).click();
  await expect(page.getByRole('group', { name: 'Delete Pebble' })).toContainText(
    'No library has copied this.',
  );
});
