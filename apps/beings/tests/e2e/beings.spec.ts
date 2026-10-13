import { expect, test } from './support/fixtures.ts';
import { person } from './support/world.ts';

test('a GM logs in and lands on the list of the only library they are in', async ({
  world,
  logInAs,
}) => {
  const page = await logInAs(world.gm);
  await expect(page).toHaveURL(`/beings/?tenant=${world.tenantId}`);
  await expect(page.getByRole('heading', { name: 'Beings' })).toBeVisible();
  for (const name of ['Ashfang', 'Brisk']) {
    await expect(page.getByRole('link', { name })).toBeVisible();
  }
});

test('says so to someone in no library yet', async ({ as }) => {
  const page = await as(await person('Newcomer'));
  await page.goto('/');
  await expect(page.getByText("You don't have access to a library yet.")).toBeVisible();
});

for (const path of ['/beings/?tenant=t', '/being/?tenant=t&id=i']) {
  test(`${path.split('?')[0]} asks you to log in first`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByText("You're not logged in. Log in to continue.")).toBeVisible();
  });
}

test('logs out', async ({ world, as }) => {
  const page = await as(world.pia);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await page.getByRole('button', { name: 'Log out' }).click();
  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();
});

test('a GM searches, and filters by kind and by campaign', async ({ world, as }) => {
  await world.npc('Goblin Chief');
  await world.playerOfAshRoad('Rhea', 'Cinder');
  const page = await as(world.gm);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  const names = page.locator('[data-being-list] [data-list] [data-name]');

  await expect(names).toHaveText(['Ashfang', 'Brisk', 'Cinder', 'Goblin Chief']);

  await page.getByRole('searchbox', { name: 'Search' }).fill('gob');
  await expect(names).toHaveText(['Goblin Chief']);
  await page.getByRole('searchbox', { name: 'Search' }).fill('');

  await page.getByLabel('Kind').selectOption('npc');
  await expect(names).toHaveText(['Goblin Chief']);
  await page.getByLabel('Kind').selectOption('character');
  await expect(names).toHaveText(['Ashfang', 'Brisk', 'Cinder']);

  await page.getByLabel('Campaign').selectOption({ label: 'Ash Road' });
  await expect(names).toHaveText(['Cinder']);
  // The filters are in the address, to share or come back to.
  await expect(page).toHaveURL(/kind=character/);
  await expect(page).toHaveURL(new RegExp(`campaign=${world.otherCampaignId}`));
});

test('a player lists the characters of the library and keeps their own with Mine', async ({
  world,
  as,
}) => {
  await world.npc('Goblin Chief');
  const page = await as(world.pia);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  const names = page.locator('[data-being-list] [data-list] [data-name]');

  // Any participant lists the library's characters, NPCs included.
  await expect(names).toHaveText(['Ashfang', 'Brisk', 'Goblin Chief']);
  // No form to make one: that is for those who run a campaign.
  await expect(page.getByRole('heading', { name: 'New being' })).toBeHidden();

  await page.getByLabel('Mine').check();
  await expect(names).toHaveText(['Ashfang']);
  await expect(page).toHaveURL(/mine=1/);
});
