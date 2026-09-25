import { expect, test } from './support/fixtures.ts';

test('a player sees what their character carries, container by container', async ({
  world,
  as,
}) => {
  const backpack = await world.item('Backpack', { tags: ['is_container'] });
  const book = await world.item('Book');
  const pack = await world.instance(backpack, { owner: world.pia });
  await world.instance(book, { owner: world.pia, container: pack });

  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('button', { name: 'Ashfang' }).click();
  await expect(page.getByRole('heading', { name: 'Backpack' })).toBeVisible();
  await expect(page.getByRole('listitem').filter({ hasText: 'Book' })).toBeVisible();
});
