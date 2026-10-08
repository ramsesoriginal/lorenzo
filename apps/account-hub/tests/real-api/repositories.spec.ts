import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import { newCampaign, newLibrary, newRepository, newUser, signedInPage } from './support';

// The rest of this file moved to studio.spec.ts (ADR 0202): a repository is run in Studio, no longer
// on /tenants. What stays is what is about the pages of playing and /beings.
test('the pages about playing leave repositories out, and /beings keeps them for reading', async ({
  browser,
}) => {
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
  for (const path of ['/campaigns']) {
    await page.goto(path);
    await expect(page.locator('#loading')).toBeHidden();
    await expect(page.locator('main')).toContainText(library.name);
    await expect(page.locator('main')).not.toContainText(repository.name);
  }

  // /beings lists both: the library's with what a GM does, the repository's for reading.
  await page.goto('/beings');
  await expect(page.locator('#loading')).toBeHidden();
  const libSection = page.locator('section', {
    has: page.getByRole('heading', { name: library.name }),
  });
  const repoSection = page.locator('section', {
    has: page.getByRole('heading', { name: new RegExp(`^${repository.name}`) }),
  });
  await expect(libSection).toContainText('Libra the Innkeeper');
  await expect(libSection.getByRole('button', { name: 'Use as a played character' })).toBeVisible();
  await expect(libSection.getByRole('button', { name: 'Create being' })).toBeVisible();
  await expect(repoSection.locator('.badge', { hasText: 'Repository' })).toBeVisible();
  await expect(repoSection).toContainText('Core the Archetype');
  await expect(repoSection.getByRole('button', { name: 'Use as a played character' })).toHaveCount(
    0,
  );
  await expect(repoSection.getByRole('button', { name: 'Rename' })).toHaveCount(0);
  await expect(repoSection.getByRole('button', { name: 'Create being' })).toHaveCount(0);
  await context.close();
});
