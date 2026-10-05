// A GM's two switches for players making their own items (ADR 0185, 0188).
import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import { addPlayer, libraryCard, newCampaign, newLibrary, newUser, signedInPage } from './support';

test("an organizer switches a campaign's players off, and one player back on", async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Zorro');
  const player = await newUser('player');
  await ok(player.api.PATCH('/me', { body: { display_name: 'Pia Player' } }));
  const seat = await addPlayer(owner.api, library.id, campaign.id, player.me.id);
  const path = { tenant_id: library.id, campaign_id: campaign.id };
  const read = async () => ({
    campaign: await ok(
      owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}', { params: { path } }),
    ),
    player: await ok(
      owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}', {
        params: { path: { ...path, player_id: seat.id } },
      }),
    ),
  });
  expect((await read()).campaign.player_self_service).toBe(true);

  const session = await signedInPage(browser, owner.subject);
  await session.page.goto('/tenants');
  const card = libraryCard(session.page, library.name);

  await card.getByRole('button', { name: 'Edit', exact: true }).click();
  await card.getByLabel('Players can make their own items').uncheck();
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(card.getByLabel('Players can make their own items')).toBeHidden();
  expect((await read()).campaign.player_self_service).toBe(false);

  const row = card.locator('li').filter({ hasText: 'Pia Player' });
  const select = row.getByLabel('Making their own items: Pia Player');
  await expect(select).toHaveValue('');
  await select.selectOption({ label: 'Can make their own items' });
  await expect(row.getByText('Saved.')).toBeVisible();
  const after = await read();
  expect(after.player.self_service).toBe(true);
  expect(after.player.self_service_effective).toBe(true);

  await select.selectOption({ label: 'Follows the campaign' });
  await expect(row.getByText('Saved.')).toBeVisible();
  const cleared = await read();
  expect(cleared.player.self_service).toBeNull();
  expect(cleared.player.self_service_effective).toBe(false);
  await session.context.close();
});
