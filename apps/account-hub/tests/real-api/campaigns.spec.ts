import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addPlayer,
  makeGm,
  newCampaign,
  newLibrary,
  newRepository,
  newUser,
  signedInPage,
} from './support';

// A campaign you run, found by the name it starts with.
function runCampaign(page: import('@playwright/test').Page, name: string) {
  return page.locator('#run-list > li').filter({ hasText: name });
}

test('a GM with only a campaign grant sees each person at the table by name, and what they play', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'The Open Table');
  const gm = await newUser('gm');
  const coGm = await newUser('co-gm');
  const pia = await newUser('pia');
  const nameless = await newUser('nameless');
  await ok(gm.api.PATCH('/me', { body: { display_name: 'Gwen GM' } }));
  await ok(coGm.api.PATCH('/me', { body: { display_name: 'Cleo Co-GM' } }));
  await ok(pia.api.PATCH('/me', { body: { display_name: 'Pia Player' } }));
  await makeGm(owner.api, library.id, campaign.id, gm.me.id);
  await makeGm(owner.api, library.id, campaign.id, coGm.me.id);
  const piaSeat = await addPlayer(owner.api, library.id, campaign.id, pia.me.id);
  await addPlayer(owner.api, library.id, campaign.id, nameless.me.id);
  await ok(
    pia.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Cael', owner_player_id: piaSeat.id, player_ids: [] },
    }),
  );

  // None of them holds a library membership: names come with the campaign's own lists.
  const { page, context } = await signedInPage(browser, gm.subject);
  await page.goto('/campaigns');
  await expect(page.locator('#loading')).toBeHidden();
  const table = runCampaign(page, 'The Open Table');
  await expect(table).toContainText(`in ${library.name}`);
  await expect(table.locator('.campaign-meta')).toContainText('GM');
  await expect(table).toContainText('Pia Player: Cael');
  // A player who set no name is listed by id, with nothing yet to play.
  await expect(table).toContainText(`${nameless.me.id}: no character yet`);
  await expect(table.getByRole('heading', { name: 'GMs' })).toBeVisible();
  await expect(table).toContainText('Gwen GM (you)');
  await expect(table).toContainText('Cleo Co-GM');
  await expect(table.getByRole('link', { name: /Manage in Your libraries/ })).toHaveAttribute(
    'href',
    '/tenants',
  );
  // Running a campaign is not playing in it.
  await expect(page.locator('#play-section')).toBeHidden();
  await context.close();
});

test('someone who plays in one campaign and runs another sees both sections, and a campaign they do both in twice', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const played = await newCampaign(owner.api, library.id, 'Hood');
  const run = await newCampaign(owner.api, library.id, 'Zorro');
  await makeGm(owner.api, library.id, run.id, owner.me.id);
  const seat = await addPlayer(owner.api, library.id, played.id, owner.me.id);
  await ok(
    owner.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Robin', owner_player_id: seat.id, player_ids: [] },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);
  await page.goto('/campaigns');
  await expect(page.locator('#loading')).toBeHidden();

  // Where you play: the seat, with its actions, as /characters had them.
  const hood = page.locator('#play-list section.campaign-subsection').filter({ hasText: 'Hood' });
  await expect(hood).toContainText('Robin');
  await expect(hood).toContainText(`in ${library.name}`);
  await expect(hood.getByRole('button', { name: 'Leave this campaign' })).toBeVisible();
  // Where you run: the GM'd campaign as GM, and the other as the library's Admin.
  await expect(runCampaign(page, 'Zorro').locator('.campaign-meta')).toContainText('GM');
  await expect(runCampaign(page, 'Hood').locator('.campaign-meta')).toContainText('Admin');
  await expect(runCampaign(page, 'Hood')).toContainText('Robin');
  await expect(page.locator('#empty-state')).toBeHidden();
  await context.close();
});

test('the seat actions are the ones /characters had: create, rename and leave', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Hood');
  const player = await newUser('player');
  await addPlayer(owner.api, library.id, campaign.id, player.me.id);

  const { page, context, confirmations } = await signedInPage(browser, player.subject);
  await page.goto('/campaigns');
  const seat = page.locator('#play-list section.campaign-subsection').filter({ hasText: 'Hood' });
  await expect(seat).toContainText("You don't have a character here yet.");
  await seat.getByPlaceholder('New character name').fill('Mira');
  await seat.getByRole('button', { name: 'Create character' }).click();
  await expect(seat).toContainText('Mira');
  await seat.getByRole('button', { name: 'Leave this campaign' }).click();
  expect(confirmations[0]).toContain('Leave "Hood"?');
  // The seat is gone, and with nothing left to show the page says so.
  await expect(page.locator('#empty-state')).toBeVisible();
  await expect(page.locator('#play-section')).toBeHidden();
  const mine = await ok(player.api.GET('/me'));
  expect(mine.players).toHaveLength(0);
  await context.close();
});

test('a library administrator who opted out of a campaign still lists it, and is told its people are not theirs to see', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Secret Table');
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);
  await page.goto('/campaigns');
  await expect(page.locator('#loading')).toBeHidden();
  const table = runCampaign(page, 'Secret Table');
  await expect(table.locator('.campaign-meta')).toContainText('Admin');
  await expect(table).toContainText("This campaign's people aren't shown to you.");
  await expect(table).not.toContainText('{');
  await context.close();
});

test('a repository is not a campaign anywhere, and a person with nothing is told so', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api);

  const { page, context } = await signedInPage(browser, owner.subject);
  await page.goto('/campaigns');
  await expect(page.locator('#loading')).toBeHidden();
  await expect(page.locator('#empty-state')).toBeVisible();
  await expect(page.locator('#empty-state')).toContainText("You don't play in or run any campaign");
  await expect(page.locator('#play-section')).toBeHidden();
  await expect(page.locator('#run-section')).toBeHidden();
  await expect(page.locator('main')).not.toContainText(repository.name);
  await context.close();
});

test('the old addresses land on the same page when signed in', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  await newCampaign(owner.api, library.id, 'The Open Table');

  const { page, context } = await signedInPage(browser, owner.subject);
  for (const old of ['/overview', '/characters']) {
    await page.goto(old);
    await expect(page).toHaveURL(/\/campaigns\/?$/);
    await expect(page.locator('#run-list')).toContainText('The Open Table');
  }
  await context.close();
});
