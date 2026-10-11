import { expect, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import { addItem, newRepository, newUser, publish, signedInPage } from './support';

async function libraryNamed(api: Api, name: string) {
  const page = await ok(api.GET('/tenants', { params: { query: { kind: 'play', size: 100 } } }));

  return page.items.find((tenant) => tenant.name === name);
}

async function itemTitles(api: Api, tenantId: string): Promise<string[]> {
  const page = await ok(
    api.GET('/tenants/{tenant_id}/items', { params: { path: { tenant_id: tenantId } } }),
  );

  return page.items.map((item) => item.title).sort();
}

async function world(options: { published?: boolean } = {}) {
  const owner = await newUser('viewer', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await addItem(owner.api, repository.id, 'Owlbear');
  if (options.published !== false) await publish(owner.api, repository.id);

  return { owner, repository, testName: `Test library: ${repository.name}` };
}

test('an Owner views a repository as a subscriber: a Test library is made once and Shelf opens for it', async ({
  browser,
}) => {
  const { owner, repository, testName } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(page.getByText('You have no Test library for this repository yet.')).toBeVisible();
  await page.getByRole('button', { name: 'View as a subscriber' }).click();

  // Shelf opens for the Test library, on this repository, which it has not copied yet.
  await expect(page).toHaveURL(/\/repositories\/\?tenant=.+&repository=/);
  await expect(page.getByRole('link', { name: 'Copy this repository' })).toBeVisible();

  const library = await libraryNamed(owner.api, testName);

  expect(library).toBeDefined();
  if (!library) return;

  // Going again opens the same one and makes no second.
  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(page.getByText('invited and has not copied')).toBeVisible();
  await page.getByRole('button', { name: 'View as a subscriber' }).click();
  await expect(page).toHaveURL(new RegExp(`tenant=${library.slug}`));

  await context.close();
});

test('Reset copies the repository into the Test library again, and Remove deletes it', async ({
  browser,
}) => {
  const { owner, repository, testName } = await world();
  const { page, context, confirmations } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await page.getByRole('button', { name: 'View as a subscriber' }).click();
  await expect(page).toHaveURL(/\/repositories\//);

  const library = await libraryNamed(owner.api, testName);

  if (!library) throw new Error('The Test library was not made.');

  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: library.id, repository_id: repository.id } },
      body: {},
    }),
  );
  expect(await itemTitles(owner.api, library.id)).toEqual(['Owlbear']);

  // The repository moves on; the Test library resets to it.
  await addItem(owner.api, repository.id, 'Griffon');
  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(page.getByText('Your Test library has copied this repository.')).toBeVisible();
  await page.getByRole('button', { name: 'Reset the Test library' }).click();
  await expect(page.locator('[data-subscriber-status]')).toHaveText(
    'The Test library has copied this repository afresh.',
  );
  expect(confirmations[0]).toContain('Reset the Test library?');
  expect(await itemTitles(owner.api, library.id)).toEqual(['Griffon', 'Owlbear']);

  await page.getByRole('button', { name: 'Remove the Test library' }).click();
  await expect(page.locator('[data-subscriber-status]')).toHaveText('The Test library is removed.');
  expect(await libraryNamed(owner.api, testName)).toBeUndefined();
  await expect(page.getByRole('button', { name: 'Reset the Test library' })).toBeHidden();

  // The repository itself is untouched.
  expect(await itemTitles(owner.api, repository.id)).toEqual(['Griffon', 'Owlbear']);
  await context.close();
});

test('a Test library that could not be invited is not left behind', async ({ browser }) => {
  const { owner, repository, testName } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.route('**/subscribers/*', (route) =>
    route.request().method() === 'PUT'
      ? route.fulfill({ status: 500, contentType: 'application/problem+json', body: '{}' })
      : route.continue(),
  );
  await page.goto(`/studio/?repository=${repository.slug}`);
  await page.getByRole('button', { name: 'View as a subscriber' }).click();

  await expect(page.locator('[data-subscriber-status]')).toHaveClass(/error-text/);
  await expect(page.locator('[data-subscriber-status]')).not.toContainText('could not be removed');
  expect(await libraryNamed(owner.api, testName)).toBeUndefined();
  await context.close();
});

test('a draft repository, and an Organizer, are not offered a Test library', async ({
  browser,
}) => {
  const draft = await world({ published: false });
  const organizer = await newUser('organizer');
  const published = await world();

  await ok(
    published.owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: published.repository.id } },
      body: { user_id: organizer.me.id, role: 'orga' },
    }),
  );

  const owner = await signedInPage(browser, draft.owner.subject);

  await owner.page.goto(`/studio/?repository=${draft.repository.slug}`);
  await expect(owner.page.getByText('Publish this repository first')).toBeVisible();
  await expect(owner.page.getByRole('button', { name: 'View as a subscriber' })).toBeHidden();
  await owner.context.close();

  const orga = await signedInPage(browser, organizer.subject);

  await orga.page.goto(`/studio/?repository=${published.repository.slug}`);
  await expect(orga.page.getByText('Only an Owner can set up a Test library.')).toBeVisible();
  await expect(orga.page.getByRole('button', { name: 'View as a subscriber' })).toBeHidden();
  await orga.context.close();
});
