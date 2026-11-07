import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addPlayer,
  newCampaign,
  newLibrary,
  newRepository,
  newUser,
  signedInPage,
} from './support';

// Home as drawn (AH1, AH6, screen 01) and the pages' width: every page in the shell's one page
// container, which follows the window or pane it is in.

test('Home is "Home" with who it is and what needs them, then what they run, play and may open', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api, `Table ${crypto.randomUUID().slice(0, 8)}`);
  const campaign = await newCampaign(owner.api, library.id, 'Harbour job');
  const repository = await newRepository(owner.api, `Draft ${crypto.randomUUID().slice(0, 8)}`);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Home', level: 1 })).toBeVisible();
  // The line under it says how many things need them: the draft is one.
  await expect(page.locator('[data-subtitle]')).toContainText('1 thing needs you');
  await expect(page.locator('[data-needs-list] > li')).toHaveCount(1);
  await expect(page.locator('[data-needs-list]')).toContainText(
    `${repository.name} is still a draft`,
  );
  await expect(page.locator('[data-needs-list]')).toContainText('You are its Owner');

  // What they run: the library with what it holds and their part, the repository, and the two ways
  // to make another.
  const run = page.locator('[data-run]');

  await expect(run.getByRole('heading', { name: 'What you run' })).toBeVisible();
  const row = run.locator('[data-run-list] > li').filter({ hasText: library.name });

  await expect(row).toContainText('1 person · 1 campaign');
  await expect(row.locator('[data-role]')).toHaveText('Owner');
  await expect(
    run.locator('[data-run-list] > li').filter({ hasText: repository.name }),
  ).toBeVisible();
  await expect(run.getByRole('link', { name: 'Set up a library' })).toBeVisible();
  await expect(run.getByRole('link', { name: 'Create a repository' })).toBeVisible();

  // Nothing is drawn for what they do not do: no seat, no Where you play.
  await expect(page.locator('[data-play]')).toBeHidden();
  expect(campaign.id).toBeTruthy();
  await context.close();
});

test('a player sees where they play and can leave from Home, after being asked', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const player = await newUser('player');
  const library = await newLibrary(owner.api, `Table ${crypto.randomUUID().slice(0, 8)}`);
  const campaign = await newCampaign(owner.api, library.id, 'Night on Station 4');

  await addPlayer(owner.api, library.id, campaign.id, player.me.id);

  const { page, context, confirmations } = await signedInPage(browser, player.subject);

  await page.goto('/');

  const row = page.locator('[data-play-list] > li').filter({ hasText: 'Night on Station 4' });

  await expect(row).toContainText(library.name);
  // A player runs nothing, and may not make a library.
  await expect(page.locator('[data-run]')).toBeHidden();

  await row.getByRole('button', { name: 'Leave' }).click();
  await expect.poll(() => confirmations[0]).toContain('Leave "Night on Station 4"?');
  await expect.poll(async () => (await ok(player.api.GET('/me'))).players.length).toBe(0);
  await context.close();
});

test('the header has the four places of the design, and the rest are behind the account button', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);

  await newLibrary(owner.api);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto('/');

  const nav = page.getByRole('banner').getByRole('navigation', { name: 'Pages' });

  await expect(nav.getByRole('link', { name: 'Home' })).toBeVisible();
  await expect(nav.getByRole('link', { name: 'Libraries' })).toBeVisible();
  await expect(nav.getByRole('link', { name: 'Repositories' })).toBeVisible();
  for (const name of ['Profile', 'Access tokens', 'Notifications', 'Set up a library']) {
    await expect(nav.getByRole('link', { name })).toHaveCount(0);
  }

  await page.getByRole('button', { name: 'Account menu' }).click();
  for (const name of [
    'Profile',
    'Notifications',
    'Libraries and people',
    'Access tokens and devices',
  ]) {
    await expect(page.getByRole('menuitem', { name })).toBeVisible();
  }
  await context.close();
});

test('every page is the one width, which is the container’s, at a desktop width', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);

  await newLibrary(owner.api);

  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 1440, height: 900 },
  });

  // Not a width for the content of a page: Home, the lists, the forms and the reading pages alike.
  for (const path of [
    '/',
    '/tenants/',
    '/repositories/',
    '/setup/',
    '/profile/',
    '/tokens/',
    '/notifications/',
  ]) {
    await page.goto(path);
    await expect(page.locator('[data-account-signed-in]')).toBeVisible();

    const box = await page.locator('#content > .shell-page').boundingBox();

    expect(box?.width, path).toBe(1120);
    // Nothing in it breaks out of it: the page does not scroll sideways.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );

    expect(overflow, path).toBeLessThanOrEqual(0);
  }

  // A window narrower than that gives the page what it has, less its gutters, and it still fits.
  await page.setViewportSize({ width: 900, height: 900 });
  await page.goto('/profile/');

  const narrow = (await page.locator('#content > .shell-page').boundingBox())?.width ?? 0;

  expect(narrow).toBeGreaterThan(800);
  expect(narrow).toBeLessThanOrEqual(900);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await context.close();
});
