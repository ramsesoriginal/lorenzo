import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { ok } from './support/api.ts';
import { signedIn, world } from './support/world.ts';

test('staff see doubled relationships and a chain whose ends do not meet; a library with none says so', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  await page.goto(`/problems/?tenant=${w.tenant.id}`);
  await expect(page.getByRole('heading', { name: 'Problems', level: 1 })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No problems found' })).toBeVisible();

  const wren = await w.entry('Wren Ashdown');
  const mara = await w.entry('Mara Quill');
  const tomas = await w.entry('Tomas Ashdown');
  const stranger = await w.entry('A Stranger');
  await w.tie('Old friends', wren.id, mara.id, true);
  await w.tie('Close friends', mara.id, wren.id, true);
  const grand = await w.tie('Wren and Tomas', wren.id, tomas.id, true);
  const up = await w.tie('Wren and Mara', wren.id, mara.id, true);
  const off = await w.tie('Stranger and Tomas', stranger.id, tomas.id, true);
  const path = { ...w.path, relationship_id: grand.id };
  const tag = (
    await w.gm.GET('/tenants/{tenant_id}/relationships/{relationship_id}/through', {
      params: { path },
    })
  ).response.headers.get('etag');
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/relationships/{relationship_id}/through', {
      params: { path },
      headers: { 'If-Match': tag ?? '' },
      body: { via: [up.id, off.id] },
    }),
  );

  await page.reload();
  const chains = page.getByRole('list', { name: 'Chains whose ends do not meet' });
  await expect(chains.getByRole('link', { name: 'Wren and Tomas' })).toBeVisible();
  const twice = page.getByRole('list', { name: 'Doubled relationships' });
  await expect(twice.getByRole('link', { name: 'Old friends' })).toBeVisible();
  await expect(twice.getByRole('link', { name: 'Close friends' })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('a player is told in one sentence that Problems are for those who manage relationships', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.playerSubject);
  await page.goto(`/problems/?tenant=${w.tenant.id}`);
  await expect(
    page.getByText('Problems are for the people who manage relationships in this library.'),
  ).toBeVisible();
  await expect(page.getByRole('list', { name: 'Doubled relationships' })).toHaveCount(0);
});
