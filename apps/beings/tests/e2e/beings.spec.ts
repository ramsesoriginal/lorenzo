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

  const kind = page.getByRole('radiogroup', { name: 'Kind' });
  await kind.getByText('NPCs').click();
  await expect(names).toHaveText(['Goblin Chief']);
  await kind.getByText('Characters', { exact: true }).click();
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
  // No button to make an NPC: that is for those who run a campaign.
  await expect(page.getByRole('button', { name: 'New being' })).toBeHidden();

  await page.getByRole('radiogroup', { name: 'Show' }).getByText('Mine').click();
  await expect(names).toHaveText(['Ashfang']);
  await expect(page.getByRole('heading', { name: 'My beings', level: 1 })).toBeVisible();
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
  const max = await world.defineStat('vitals', 'hit_points_max', 'int');
  const hp = await world.defineStat('vitals', 'hit_points', 'int', {
    pin: true,
    adjustable_in_play: true,
    max_hint_id: max.id,
  });
  const body = await world.defineStat('vitals', 'body', 'int');
  const ashfang = world.pia.character.entity_id;
  await world.setStat(ashfang, max.id, 20);
  await world.setStat(ashfang, hp.id, 14);
  await world.setStat(ashfang, body.id, 3);
  const page = await as(world.gm);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  const view = page.getByRole('radiogroup', { name: 'View' });
  const list = page.locator('[data-being-list] [data-list]');

  // Rows are the default: a table with who plays each and the pinned numbers.
  await expect(view.getByRole('radio', { name: 'Rows' })).toBeChecked();
  const table = page.getByRole('table', { name: 'Beings' });
  await expect(table.getByRole('columnheader')).toHaveText([
    'Name',
    'Kind',
    'Played by',
    'Hit points',
    'Body',
  ]);
  const row = table.getByRole('row').filter({ hasText: 'Ashfang' });
  await expect(row.getByRole('cell').nth(1)).toHaveText('Character');
  await expect(row.getByRole('cell').nth(2)).toHaveText(/Pia/);
  await expect(row.getByRole('cell').nth(3)).toHaveText('14 / 20');
  await expect(row.getByRole('cell').nth(4)).toHaveText('3');

  await view.getByText('Cards').click();
  const card = list.locator('.being-card', { hasText: 'Ashfang' });
  await expect(card.locator('.card-number')).toContainText('14');
  await expect(card.locator('.card-number')).toContainText('/ 20');
  await expect(card.locator('.card-number')).toContainText('hit points');

  await view.getByText('Side by side').click();
  const side = page.getByRole('region', { name: 'Beings side by side' }).locator('table');
  await expect(side.getByRole('columnheader', { name: /Ashfang/ })).toBeVisible();
  // The limit sits beside the number; it is not a row of its own.
  await expect(side.getByRole('rowheader', { name: 'Hit points max' })).toHaveCount(0);
  await expect(side.getByRole('rowheader', { name: 'Hit points', exact: true })).toBeVisible();
  await expect(
    side
      .locator('tr', { has: page.getByRole('rowheader', { name: 'Played by' }) })
      .locator('td')
      .first(),
  ).toHaveText(/Pia/);
  const bodyRow = side.locator('tr', { has: page.getByRole('rowheader', { name: 'Body' }) });
  await expect(bodyRow.locator('td').first()).toHaveText('3');
  await expect(list).toBeHidden();

  // The choice comes back, and a search narrows the table.
  await page.reload();
  await expect(view.getByRole('radio', { name: 'Side by side' })).toBeChecked();
  await page.getByRole('searchbox', { name: 'Search' }).fill('ashf');
  await expect(side.getByRole('columnheader')).toHaveCount(2);
});

test('side by side has Play: steppers on the numbers a person may run, and Undo', async ({
  world,
  as,
}) => {
  const hp = await world.defineStat('vitals', 'hit_points', 'int', {
    pin: true,
    adjustable_in_play: true,
  });
  const ashfang = world.pia.character.entity_id;
  const brisk = world.oskar.character.entity_id;
  await world.setStat(ashfang, hp.id, 9);
  await world.setStat(brisk, hp.id, 7);

  // A player runs their own being only.
  const page = await as(world.pia);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();
  await page.getByRole('radiogroup', { name: 'View' }).getByText('Side by side').click();
  const side = page.getByRole('region', { name: 'Beings side by side' });
  await expect(side.getByRole('columnheader', { name: /Brisk/ })).toBeVisible();
  await expect(side.getByRole('button', { name: /Lower/ })).toHaveCount(0);

  await page.getByRole('radiogroup', { name: 'Mode' }).getByText('Play').click();
  await expect(side.getByRole('button', { name: /Lower Hit points of/ })).toHaveCount(1);
  await side.getByRole('button', { name: 'Lower Hit points of Ashfang' }).click();
  await expect(side.locator('td', { hasText: /^8/ })).toHaveCount(1);
  await expect(page.locator('[data-shell-toasts]')).toContainText('Ashfang: Hit points 9 → 8');

  await page.getByRole('button', { name: 'Undo', exact: true }).first().click();
  await expect(side.locator('td', { hasText: /^9/ })).toHaveCount(1);
});

test('a GM makes a being from the New being dialog, and the list says when there is none', async ({
  world,
  as,
}) => {
  const page = await as(world.gm);
  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await expect(page.getByRole('heading', { name: 'All beings', level: 1 })).toBeVisible();
  await expect(page.getByText('The characters of')).toBeVisible();

  await page.getByRole('searchbox', { name: 'Search' }).fill('zzz');
  await expect(page.getByText('Nothing matches.')).toBeVisible();
  await page.getByRole('button', { name: 'Clear the search' }).click();
  await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();

  await page.getByRole('button', { name: 'New being' }).click();
  const dialog = page.getByRole('dialog', { name: 'New being' });
  await dialog.getByLabel('Name').fill('Thorn');
  await dialog.getByRole('button', { name: 'Create being' }).click();
  await expect(page.getByRole('heading', { name: 'Thorn', level: 1 })).toBeVisible();
});
