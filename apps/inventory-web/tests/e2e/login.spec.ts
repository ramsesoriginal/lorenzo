import { expect, test } from './support/fixtures.ts';

test('a player logs in and finds the tenant they play in', async ({ world, as }) => {
  const page = await as(world.pia);
  await expect(page.getByText('Signed in as')).toContainText(world.pia.subject);
  await page.getByRole('link', { name: world.tenantName }).click();
  await expect(page).toHaveURL(`/board/?tenant=${world.tenantId}`);
});
