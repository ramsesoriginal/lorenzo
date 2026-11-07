import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addPlayer,
  campaignCard,
  makeGm,
  newCampaign,
  newLibrary,
  newUser,
  openLibrary,
  seatFor,
  signedInPage,
} from './support';

// A campaign lives in its library (ADR 0428): the card holds the people at the table for those who
// manage it and the person's own seat for those who play.

test('a GM with only a campaign grant sees each person at the table by name, and what they play', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'The Open Table');
  const gm = await newUser('gm');
  const pia = await newUser('pia');
  await ok(gm.api.PATCH('/me', { body: { display_name: 'Gwen GM' } }));
  await ok(pia.api.PATCH('/me', { body: { display_name: 'Pia Player' } }));
  await makeGm(owner.api, library.id, campaign.id, gm.me.id);
  const piaSeat = await addPlayer(owner.api, library.id, campaign.id, pia.me.id);
  await ok(
    pia.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Cael', owner_player_id: piaSeat.id, player_ids: [] },
    }),
  );

  // The GM holds no library membership: names come with the campaign's own lists.
  const { page, context } = await signedInPage(browser, gm.subject);
  const card = campaignCard(await openLibrary(page, library), 'The Open Table');
  await expect(card.locator('[data-campaign-meta]')).toContainText('GM');
  await expect(card).toContainText('Pia Player');
  await expect(card).toContainText('Cael');
  // Running a campaign is not playing in it.
  await expect(card.locator('[data-seat]')).toHaveCount(0);
  await context.close();
});

test('someone who plays in one campaign and runs another sees both in their library', async ({
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
  const cards = await openLibrary(page, library);

  // The seat, with its actions, inside the campaign it belongs to.
  const hood = seatFor(page, 'Hood');
  await expect(hood).toContainText('Robin');
  await expect(hood.getByRole('button', { name: 'Leave this campaign' })).toBeVisible();
  await expect(campaignCard(cards, 'Zorro').locator('[data-campaign-meta]')).toContainText('GM');
  await expect(seatFor(page, 'Zorro')).toHaveCount(0);
  await context.close();
});

test('the seat actions are create, rename and leave', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Hood');
  const player = await newUser('player');
  await addPlayer(owner.api, library.id, campaign.id, player.me.id);

  const { page, context, confirmations } = await signedInPage(browser, player.subject);
  await openLibrary(page, library);
  const seat = seatFor(page, 'Hood');
  await expect(seat).toContainText("You don't have a character here yet.");
  await seat.getByPlaceholder('New character name').fill('Mira');
  await seat.getByRole('button', { name: 'Create character' }).click();
  await expect(seat).toContainText('Mira');
  await seat.getByRole('button', { name: 'Leave this campaign' }).click();
  expect(confirmations[0]).toContain('Leave "Hood"?');
  await expect.poll(async () => (await ok(player.api.GET('/me'))).players.length).toBe(0);
  await context.close();
});

test('the old addresses land on the libraries when signed in', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  await newCampaign(owner.api, library.id, 'The Open Table');

  const { page, context } = await signedInPage(browser, owner.subject);
  for (const old of ['/overview', '/characters', '/campaigns']) {
    await page.goto(old);
    await expect(page).toHaveURL(/\/tenants\/?(\?.*)?$/);
    await expect(page.locator('[data-campaign-list]')).toContainText('The Open Table');
  }
  await context.close();
});
