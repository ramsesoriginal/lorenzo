import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import { newCampaign, newLibrary, newRepository, newUser, signedInPage } from './support';

// The rest of this file moved to studio.spec.ts (ADR 0202): a repository is run in Studio, no longer
// on /tenants. What stays is what is about the pages of playing.
test('the pages about playing leave repositories out', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'The Open Table');
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: {
        path: { tenant_id: library.id, campaign_id: campaign.id, user_id: owner.me.id },
      },
    }),
  );
  await ok(
    owner.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Libra the Innkeeper', player_ids: [] },
    }),
  );
  const repository = await newRepository(owner.api);
  await ok(
    owner.api.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: repository.id } },
      body: { name: 'Core the Archetype', player_ids: [] },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  // Nobody plays in a repository: it is on neither of these.
  for (const path of ['/tenants']) {
    await page.goto(path);
    await expect(page.locator('#loading')).toBeHidden();
    await expect(page.locator('main')).toContainText(library.name);
    await expect(page.locator('main')).not.toContainText(repository.name);
  }

  await context.close();
});
