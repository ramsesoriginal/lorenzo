import { expect, test } from './support/fixtures.ts';
import { person } from './support/world.ts';

test('a player logs in and finds the tenant they play in', async ({ world, as }) => {
  const page = await as(world.pia);
  await expect(page.getByText('Signed in as')).toContainText(world.pia.subject);
  await page.getByRole('link', { name: world.tenantName }).click();
  await expect(page).toHaveURL(`/board/?tenant=${world.tenantId}`);
});

test('logs out', async ({ world, as }) => {
  const page = await as(world.pia);
  await page.getByRole('button', { name: 'Log out' }).click();
  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();
});

test('says so to someone in no tenant yet', async ({ as }) => {
  const page = await as(await person('Newcomer'));
  await expect(page.getByText("You don't belong to any tenant yet.")).toBeVisible();
});

for (const path of ['/board/?tenant=t', '/item/?tenant=t&id=i', '/items/?tenant=t']) {
  test(`${path.split('?')[0]} asks you to log in first`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByText("You're not logged in. Log in to continue.")).toBeVisible();
  });
}
