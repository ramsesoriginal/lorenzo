import { expect, test } from '@playwright/test';
import { apiAs, ok } from '../../../inventory-web/tests/e2e/support/api';
import { AUTHGEAR_URL, SUBJECT_COOKIE } from '../../../inventory-web/tests/e2e/support/env';
import { newCampaign, newLibrary, newUser, signedInPage } from './support';

test('a library admin who GMs a campaign hands a being to a player, named by display name', async ({
  page,
  context,
}) => {
  const subject = `hub-owner-${crypto.randomUUID()}`;
  const owner = await apiAs(subject, ['tenant_creator']);
  await ok(owner.GET('/me'));
  const tenant = await ok(
    owner.POST('/tenants', { body: { name: `World ${crypto.randomUUID()}` } }),
  );
  const campaign = await ok(
    owner.POST('/tenants/{tenant_id}/campaigns', {
      params: { path: { tenant_id: tenant.id } },
      body: {
        name: 'Handoff',
        slug: 'handoff',
        description: '',
        game_system: 'test',
        secret: false,
      },
    }),
  );
  const ownerMe = await ok(owner.GET('/me'));
  await ok(
    owner.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { tenant_id: tenant.id, campaign_id: campaign.id, user_id: ownerMe.id } },
    }),
  );
  const being = await ok(
    owner.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: tenant.id } },
      body: { name: 'Goblin', player_ids: [] },
    }),
  );
  // A player who is not a library member: the hand-off panel names them from the roster.
  const player = await apiAs(`hub-player-${crypto.randomUUID()}`);
  const playerMe = await ok(player.GET('/me'));
  await ok(player.PATCH('/me', { body: { display_name: 'Pia Player' } }));
  const seat = await ok(
    owner.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: tenant.id, campaign_id: campaign.id } },
      body: { user_id: playerMe.id },
    }),
  );

  await context.addCookies([{ name: SUBJECT_COOKIE, value: subject, url: AUTHGEAR_URL }]);
  await page.goto('/');
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.locator('#account-signed-in')).toBeVisible();
  await page.goto('/beings');
  const row = page.locator('li').filter({ hasText: 'Goblin' });
  await row.getByRole('button', { name: 'Use as a played character' }).click();
  await row.getByRole('combobox').selectOption({ label: 'Handoff' });
  const choice = row.locator('li').filter({ hasText: 'Pia Player' });
  await expect(choice).toBeVisible();
  await expect(row).not.toContainText(playerMe.id);
  await choice.getByRole('button', { name: 'Use this player' }).click();

  await expect
    .poll(async () => {
      const handed = await ok(
        owner.GET('/tenants/{tenant_id}/characters/{character_id}', {
          params: { path: { tenant_id: tenant.id, character_id: being.entity_id } },
        }),
      );
      return handed.owner_player_id;
    })
    .toBe(seat.id);
});

// ADR 0173: a GM with no library membership lists the beings in their reach, so /beings and its
// hand-off panel open for them. Before it, GET .../beings answered them with a 404 and the whole
// page showed "No tenant with id ...".
test('a campaign GM with no library membership hands over a being, and sees no other table', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const hood = await newCampaign(owner.api, library.id, 'Hood');
  const zorro = await newCampaign(owner.api, library.id, 'Zorro');
  const gm = await newUser('gm');
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { tenant_id: library.id, campaign_id: hood.id, user_id: gm.me.id } },
    }),
  );
  const pia = await newUser('pia');
  const seat = await ok(
    owner.api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: library.id, campaign_id: hood.id } },
      body: { user_id: pia.me.id },
    }),
  );
  // A being in no campaign, and a player character at the other table.
  const goblin = await ok(
    owner.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Goblin', player_ids: [] },
    }),
  );
  const brisk = await newUser('brisk');
  const briskSeat = await ok(
    owner.api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: library.id, campaign_id: zorro.id } },
      body: { user_id: brisk.me.id },
    }),
  );
  await ok(
    owner.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Brisk the Bold', owner_player_id: briskSeat.id, player_ids: [] },
    }),
  );

  const session = await signedInPage(browser, gm.subject);
  await session.page.goto('/beings');
  await expect(session.page.locator('#load-error')).toBeHidden();
  const list = session.page.locator('#tenant-list');
  await expect(list).toContainText('Goblin');
  await expect(list).not.toContainText('Brisk the Bold');

  const row = list.locator('li').filter({ hasText: 'Goblin' });
  await row.getByRole('button', { name: 'Use as a played character' }).click();
  await row.getByRole('combobox').selectOption({ label: 'Hood' });
  // No roster read without a membership, so the player is shown by user id.
  const choice = row.locator('li').filter({ hasText: pia.me.id });
  await expect(choice).toBeVisible();
  await choice.getByRole('button', { name: 'Use this player' }).click();

  await expect
    .poll(async () => {
      const handed = await ok(
        owner.api.GET('/tenants/{tenant_id}/characters/{character_id}', {
          params: { path: { tenant_id: library.id, character_id: goblin.entity_id } },
        }),
      );
      return handed.owner_player_id;
    })
    .toBe(seat.id);
  await session.context.close();
});
