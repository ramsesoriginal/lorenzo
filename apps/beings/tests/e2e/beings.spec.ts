import { ok } from './support/api.ts';
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
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();
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

test('the pages sit in the web shell: its navigation, the account menu and, with two libraries, the switcher', async ({
  world,
  as,
}) => {
  const page = await as(world.gm);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeAttached();
  const pages = page.getByRole('navigation', { name: 'Pages' });
  await expect(pages.getByRole('link', { name: 'Beings', exact: true })).toHaveAttribute(
    'aria-current',
    'page',
  );
  await expect(pages.getByRole('link', { name: 'Libraries' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Library or repository' })).toBeHidden();

  await ok(world.gm.api.POST('/tenants', { body: { name: 'Second library' } }));
  await page.reload();
  const switcher = page.getByRole('combobox', { name: 'Library or repository' });
  await expect(switcher).toBeVisible();
  await switcher.selectOption({ label: 'Second library' });
  await expect(page).toHaveURL(/\/beings\/\?tenant=/);
  await expect(page).not.toHaveURL(new RegExp(world.tenantId));
});

test('the list has rows, cards and side by side, and keeps the one chosen', async ({
  world,
  as,
}) => {
  const hp = await world.defineStat('vitals', 'hit_points', 'int', { pin: true });
  const body = await world.defineStat('vitals', 'body', 'int');
  const ashfang = world.pia.character.entity_id;
  await world.setStat(ashfang, hp.id, 14);
  await world.setStat(ashfang, body.id, 3);
  const page = await as(world.gm);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  const view = page.getByRole('radiogroup', { name: 'View' });
  const list = page.locator('[data-being-list] [data-list]');

  // Rows are the default, and show no numbers.
  await expect(list.locator('li')).toHaveCount(2);
  await expect(view.getByRole('radio', { name: 'Rows' })).toBeChecked();
  await expect(list.locator('[data-vital]:visible')).toHaveCount(0);

  await view.getByText('Cards').click();
  await expect(list).toHaveClass(/being-cards/);
  await expect(list.locator('li', { hasText: 'Ashfang' }).locator('[data-vital]')).toContainText(
    '14',
  );

  await view.getByText('Side by side').click();
  const table = page.getByRole('region', { name: 'Beings side by side' }).locator('table');
  await expect(table.getByRole('columnheader', { name: /Ashfang/ })).toBeVisible();
  await expect(table.getByRole('rowheader', { name: 'Body' })).toBeVisible();
  const row = table.locator('tr', { has: page.getByRole('rowheader', { name: 'Body' }) });
  await expect(row.locator('td').first()).toHaveText('3');
  await expect(list).toBeHidden();

  // The choice comes back, and a search narrows the table.
  await page.reload();
  await expect(view.getByRole('radio', { name: 'Side by side' })).toBeChecked();
  await page.getByRole('searchbox', { name: 'Search' }).fill('ashf');
  await expect(table.getByRole('columnheader')).toHaveCount(2);
});
