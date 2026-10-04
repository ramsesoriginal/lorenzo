import { expect, test } from '@playwright/test';
import { type apiAs, ok } from '../../../inventory-web/tests/e2e/support/api';
import { libraryCard, newCampaign, newLibrary, newUser, signedInPage } from './support';

async function addPlayer(
  owner: Awaited<ReturnType<typeof apiAs>>,
  tenantId: string,
  campaignId: string,
  userId: string,
) {
  return ok(
    owner.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
      body: { user_id: userId },
    }),
  );
}

async function setup() {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Zorro');
  return { owner, library, campaign };
}

test('a library admin removes a player, named on the roster, from a campaign', async ({
  browser,
}) => {
  const { owner, library, campaign } = await setup();
  const player = await newUser('player');
  await ok(player.api.PATCH('/me', { body: { display_name: 'Pia Player' } }));
  await addPlayer(owner.api, library.id, campaign.id, player.me.id);

  const session = await signedInPage(browser, owner.subject);
  await session.page.goto('/tenants');
  const row = libraryCard(session.page, library.name)
    .locator('li')
    .filter({ hasText: 'Pia Player' });
  await row.getByRole('button', { name: 'Remove', exact: true }).click();
  await expect(libraryCard(session.page, library.name)).not.toContainText('Pia Player');
  expect(session.confirmations[0]).toContain('Remove Pia Player from "Zorro"?');
  const players = await ok(
    owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
    }),
  );
  expect(players.items).toEqual([]);
  await session.context.close();
});

test('a campaign GM with no library membership sees the players, and removes one', async ({
  browser,
}) => {
  const { owner, library, campaign } = await setup();
  const gm = await newUser('gm');
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id, user_id: gm.me.id } },
    }),
  );
  const player = await newUser('player');
  await addPlayer(owner.api, library.id, campaign.id, player.me.id);

  const session = await signedInPage(browser, gm.subject);
  await session.page.goto('/tenants');
  // No roster read without a Membership, so the player is shown by user id.
  const row = libraryCard(session.page, library.name)
    .locator('li')
    .filter({ hasText: player.me.id });
  await row.getByRole('button', { name: 'Remove', exact: true }).click();
  await expect(libraryCard(session.page, library.name)).not.toContainText(player.me.id);
  const players = await ok(
    owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
    }),
  );
  expect(players.items).toEqual([]);
  await session.context.close();
});

test('a player undoes a reused character; an owner link is never offered', async ({ browser }) => {
  const { owner, library, campaign } = await setup();
  const second = await newCampaign(owner.api, library.id, 'Hood');
  const player = await newUser('player');
  const seat1 = await addPlayer(owner.api, library.id, campaign.id, player.me.id);
  const seat2 = await addPlayer(owner.api, library.id, second.id, player.me.id);
  const character = await ok(
    player.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Cael', owner_player_id: seat1.id, player_ids: [] },
    }),
  );
  await ok(
    player.api.PUT('/tenants/{tenant_id}/characters/{character_id}/players/{player_id}', {
      params: {
        path: { tenant_id: library.id, character_id: character.entity_id, player_id: seat2.id },
      },
    }),
  );

  const session = await signedInPage(browser, player.subject);
  await session.page.goto('/characters');
  const zorro = session.page.locator('section.campaign-subsection').filter({ hasText: 'Zorro' });
  const hood = session.page.locator('section.campaign-subsection').filter({ hasText: 'Hood' });
  await expect(zorro).toContainText('Cael');
  await expect(hood).toContainText('Cael');
  await expect(zorro.getByRole('button', { name: 'Stop using in this campaign' })).toHaveCount(0);
  await hood.getByRole('button', { name: 'Stop using in this campaign' }).click();
  await expect(hood).toContainText("You don't have a character here yet.");
  expect(session.confirmations[0]).toContain('Stop using "Cael" in "Hood"?');
  const after = await ok(
    player.api.GET('/tenants/{tenant_id}/characters/{character_id}', {
      params: { path: { tenant_id: library.id, character_id: character.entity_id } },
    }),
  );
  expect(after.players.map((p) => p.id)).toEqual([seat1.id]);
  await session.context.close();
});

test('a campaign manager unlinks a character, but never its owner', async ({ browser }) => {
  const { owner, library, campaign } = await setup();
  const second = await newCampaign(owner.api, library.id, 'Hood');
  const player = await newUser('player');
  await ok(player.api.PATCH('/me', { body: { display_name: 'Pia Player' } }));
  const seat1 = await addPlayer(owner.api, library.id, campaign.id, player.me.id);
  const seat2 = await addPlayer(owner.api, library.id, second.id, player.me.id);
  const character = await ok(
    player.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Cael', owner_player_id: seat1.id, player_ids: [] },
    }),
  );
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/characters/{character_id}/players/{player_id}', {
      params: {
        path: { tenant_id: library.id, character_id: character.entity_id, player_id: seat2.id },
      },
    }),
  );
  const links = () =>
    ok(
      owner.api.GET('/tenants/{tenant_id}/characters/{character_id}', {
        params: { path: { tenant_id: library.id, character_id: character.entity_id } },
      }),
    ).then((c) => c.players.map((p) => p.id).sort());

  const session = await signedInPage(browser, owner.subject);
  await session.page.goto('/tenants');
  const card = libraryCard(session.page, library.name);
  const zorroRow = card
    .locator('li')
    .filter({ hasText: 'Zorro' })
    .locator('li')
    .filter({ hasText: 'Pia Player' });
  const hoodRow = card
    .locator('li')
    .filter({ hasText: 'Hood' })
    .locator('li')
    .filter({ hasText: 'Pia Player' });

  // The owner's own link: refused in words, nothing changes.
  await zorroRow.getByRole('button', { name: 'Unlink' }).click();
  await expect(zorroRow).toContainText('is owned by Pia Player here, so the link stays');
  expect(await links()).toEqual([seat1.id, seat2.id].sort());

  // The reused link goes.
  await hoodRow.getByRole('button', { name: 'Unlink' }).click();
  await expect(hoodRow).not.toContainText('Cael');
  expect(await links()).toEqual([seat1.id]);
  await session.context.close();
});

test('an organizer edits a library name and description, and sees the new name at once', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}', {
      params: { path: { tenant_id: library.id } },
      body: { description: 'The first draft.' },
    }),
  );

  const session = await signedInPage(browser, owner.subject);
  await session.page.goto('/tenants');
  const card = libraryCard(session.page, library.name);
  await card.getByRole('button', { name: 'Edit library' }).click();
  await expect(card.getByLabel('Description')).toHaveValue('The first draft.');
  const name = `Renamed ${crypto.randomUUID()}`;
  await card.getByLabel('Library name').fill(name);
  await card.getByLabel('Description').fill('A better one.');
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(session.page.getByRole('heading', { name: new RegExp(`^${name}`) })).toBeVisible();
  const saved = await ok(
    owner.api.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: library.id } } }),
  );
  expect(saved.name).toBe(name);
  expect(saved.description).toBe('A better one.');
  expect(saved.slug).toBe(library.slug);

  // A taken slug is the API's own sentence, not a body.
  const other = await newLibrary(owner.api);
  const renamedCard = libraryCard(session.page, name);
  await renamedCard.getByRole('button', { name: 'Edit library' }).click();
  await renamedCard.getByLabel('Library slug').fill(other.slug);
  await renamedCard.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(renamedCard.locator('.tenant-details')).not.toContainText('{');
  await expect(renamedCard.locator('.tenant-details')).toContainText(/already in use|taken/i);
  await session.context.close();
});
