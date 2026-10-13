import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import { addPlayer, newCampaign, newLibrary, newUser, signedInPage } from './support';

test('a player opens a library without reading other public campaigns details', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const played = await newCampaign(owner.api, library.id, 'My table');
  const other = await newCampaign(owner.api, library.id, 'Another public table');
  for (const campaign of [played, other]) {
    await ok(
      owner.api.PATCH('/tenants/{tenant_id}/campaigns/{campaign_id}', {
        params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
        body: { description: `${campaign.name} description` },
      }),
    );
  }
  const player = await newUser('player');
  await addPlayer(owner.api, library.id, played.id, player.me.id);
  const me = await ok(player.api.GET('/me'));
  expect(me.memberships).toHaveLength(0);
  expect(me.campaign_gm_grants).toHaveLength(0);
  const denied = await player.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}', {
    params: { path: { tenant_id: library.id, campaign_id: other.id } },
  });
  expect(denied.response.status).toBe(404);

  const { context, page } = await signedInPage(browser, player.subject);
  try {
    const detailRequests: string[] = [];
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname;
      if (request.method() === 'GET' && path.startsWith(`/tenants/${library.id}/campaigns/`)) {
        detailRequests.push(path);
      }
    });
    await page.goto(`/tenants/?tenant=${library.slug}`);
    const panel = page.locator('[data-tenant]');
    await expect(panel.locator('[data-loading]')).toBeHidden();
    await expect(panel.locator('[data-error]')).toBeHidden();
    await expect(panel.locator('[data-campaign-name]')).toHaveText([other.name, played.name]);
    await expect(
      panel.locator('[data-campaign-description]').filter({ hasText: 'My table description' }),
    ).toBeVisible();
    await expect(panel).not.toContainText('Another public table description');
    expect(detailRequests).toContain(`/tenants/${library.id}/campaigns/${played.id}`);
    expect(detailRequests).not.toContain(`/tenants/${library.id}/campaigns/${other.id}`);
    await expect(panel.getByRole('button', { name: 'Edit library' })).toHaveCount(0);
  } finally {
    await context.close();
  }
});
