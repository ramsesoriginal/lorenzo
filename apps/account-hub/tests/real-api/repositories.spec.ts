import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  libraryCard,
  newCampaign,
  newLibrary,
  newRepository,
  newUser,
  repositoryCard,
  signedInPage,
} from './support';

test('a library and a repository sit side by side, each with only what fits it', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  await newCampaign(owner.api, library.id, 'The Open Table');
  const repository = await newRepository(owner.api);

  const { page, context } = await signedInPage(browser, owner.subject);
  await page.goto('/tenants');

  // The library is a library: its campaigns and the form to make one.
  const lib = libraryCard(page, library.name);
  await expect(lib).toBeVisible();
  await expect(lib).toContainText('The Open Table');
  await expect(lib.getByRole('button', { name: 'Edit library' })).toBeVisible();

  // The repository is not in that list, and is in its own section, called what it is.
  await expect(page.locator('#tenant-list')).not.toContainText(repository.name);
  await expect(page.getByRole('heading', { name: 'Your repositories' })).toBeVisible();
  const repo = repositoryCard(page, repository.name);
  await expect(repo).toBeVisible();
  await expect(repo.locator('.badge', { hasText: 'Repository' })).toBeVisible();
  await expect(repo.locator('.repository-status')).toHaveText('Draft');
  await expect(repo.getByRole('button', { name: 'Edit repository' })).toBeVisible();
  await expect(repo.getByRole('heading', { name: 'Repository admins' })).toBeVisible();
  await expect(repo.getByRole('button', { name: 'Leave this repository' })).toBeVisible();
  // Nothing that only makes sense where people play.
  await expect(repo).not.toContainText('campaign');
  await expect(repo.getByRole('heading', { name: 'Library admins' })).toHaveCount(0);
  await expect(repo.getByRole('button', { name: 'Leave this library' })).toHaveCount(0);
  await expect(repo.getByText('Invite a player')).toHaveCount(0);

  // Publishing stays on the CLI/API; the page only reads it.
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/published', {
      params: { path: { tenant_id: repository.id } },
    }),
  );
  await page.reload();
  await expect(repositoryCard(page, repository.name).locator('.repository-status')).toHaveText(
    /^Published \d{4}-\d{2}-\d{2}$/,
  );
  await context.close();
});

test('a repository is renamed and left in its own words', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const coOwner = await newUser('co-owner');
  const repository = await newRepository(owner.api);
  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: repository.id } },
      body: { user_id: coOwner.me.id, role: 'owner' },
    }),
  );

  const { page, context, confirmations } = await signedInPage(browser, owner.subject);
  await page.goto('/tenants');
  const renamed = `Renamed ${crypto.randomUUID()}`;
  const repo = repositoryCard(page, repository.name);
  await repo.getByRole('button', { name: 'Edit repository' }).click();
  await repo.getByLabel('Repository name').fill(renamed);
  await repo.getByRole('button', { name: 'Save' }).click();
  await expect(repositoryCard(page, renamed)).toBeVisible();
  const saved = await ok(
    owner.api.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: repository.id } } }),
  );
  expect(saved.name).toBe(renamed);
  expect(saved.kind).toBe('repository');

  await repositoryCard(page, renamed)
    .getByRole('button', { name: 'Leave this repository' })
    .click();
  await expect(repositoryCard(page, renamed)).toHaveCount(0);
  expect(confirmations[0]).toContain(`Leave "${renamed}"?`);
  expect(confirmations[0]).toContain('this repository');
  expect(confirmations[0].toLowerCase()).not.toContain('library');
  const remaining = await ok(owner.api.GET('/tenants'));
  expect(remaining.items.map((t) => t.id)).not.toContain(repository.id);
  await context.close();
});

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

test('the create forms are for accounts the API says may create, and each makes its own kind', async ({
  browser,
}) => {
  // An account without the role is told so, once, and offered no form.
  const plain = await newUser('plain');
  const refused = await signedInPage(browser, plain.subject);
  await refused.page.goto('/tenants');
  await expect(refused.page.locator('#loading')).toBeHidden();
  await expect(refused.page.locator('#create-unavailable')).toBeVisible();
  await expect(refused.page.locator('#create-unavailable')).toContainText(
    "isn't open to your account yet",
  );
  await expect(refused.page.locator('.create-tenant-form')).toHaveCount(0);
  await expect(refused.page.locator('#repositories-section')).toBeHidden();
  await refused.context.close();

  // An account with it gets both, and a repository made from the page is one.
  const maker = await newUser('maker', ['tenant_creator']);
  const { page, context } = await signedInPage(browser, maker.subject);
  await page.goto('/tenants');
  await expect(page.locator('#create-unavailable')).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Create a library' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Create a repository' })).toBeVisible();
  const name = `Made ${crypto.randomUUID()}`;
  const form = page.locator('#create-repository-container form');
  await form.getByLabel('Repository name').fill(name);
  await form.getByRole('button', { name: 'Create repository' }).click();
  await expect(repositoryCard(page, name)).toBeVisible();
  await expect(page.locator('#tenant-list')).not.toContainText(name);

  const mine = await ok(maker.api.GET('/tenants'));
  expect(mine.items.find((t) => t.name === name)?.kind).toBe('repository');

  // And a library from the other form stays a library.
  const libraryName = `Made library ${crypto.randomUUID()}`;
  const libraryForm = page.locator('#create-tenant-container form');
  await libraryForm.getByLabel('Library name').fill(libraryName);
  await libraryForm.getByRole('button', { name: 'Create library' }).click();
  await expect(libraryCard(page, libraryName)).toBeVisible();
  const after = await ok(maker.api.GET('/tenants'));
  expect(after.items.find((t) => t.name === libraryName)?.kind).toBe('play');
  await context.close();
});
