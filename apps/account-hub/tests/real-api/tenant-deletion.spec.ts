import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  invite,
  newCampaign,
  newLibrary,
  newRepository,
  newUser,
  openLibrary,
  publish,
  signedInPage,
} from './support';

// Deleting a library or repository from the hub (ADR 0267, on the route of ADR 0184).

async function addMember(owner: Awaited<ReturnType<typeof newUser>>, id: string, role: string) {
  const person = await newUser(role);

  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: id } },
      body: { user_id: person.me.id, role: role as 'owner' | 'orga' },
    }),
  );

  return person;
}

async function openDeleteDialog(page: Page, section: ReturnType<Page['locator']>) {
  await section.getByRole('button', { name: /^Delete this (library|repository)…$/ }).click();

  const dialog = page.getByRole('dialog');

  await expect(dialog).toBeVisible();

  return dialog;
}

test('an Owner deletes a library only after typing its name, and lands on the list with a message', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const other = await newLibrary(owner.api, `Other ${crypto.randomUUID().slice(0, 8)}`);
  const library = await newLibrary(owner.api, `Doomed ${crypto.randomUUID().slice(0, 8)}`);

  await newCampaign(owner.api, library.id, 'Zorro');
  await newCampaign(owner.api, library.id, 'Hawk');
  await addMember(owner, library.id, 'orga');

  const { page, context } = await signedInPage(browser, owner.subject);
  const article = await openLibrary(page, library);

  await article.locator('[data-tenant-tabs] > .tabs').getByRole('tab', { name: 'People' }).click();

  const dialog = await openDeleteDialog(page, article);
  const confirm = dialog.getByRole('button', { name: 'Delete this library', exact: true });

  // What is lost, from what the tab already read and one count of the entries.
  await expect(dialog).toContainText('2 campaigns');
  // A campaign is an entry of the library too, so the count is the API's, not a guess.
  await expect(dialog).toContainText(/\d+ entries/);
  await expect(dialog).toContainText('2 people with a role');
  await expect(dialog).toContainText(
    `This deletes "${library.name}" and everything in it for good`,
  );

  // A wrong name, or none, keeps the button off.
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel(`Type "${library.name}" to confirm`).fill('not the name');
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel(`Type "${library.name}" to confirm`).fill(library.name.toLowerCase());
  await expect(confirm).toBeDisabled();
  expect((await ok(owner.api.GET('/tenants'))).items.map((t) => t.id)).toContain(library.id);

  await dialog.getByLabel(`Type "${library.name}" to confirm`).fill(library.name);
  await expect(confirm).toBeEnabled();
  await confirm.click();

  // It leaves for the list: the library is gone from it, the message is shown, another is open.
  await expect(page.locator('[data-notice]')).toHaveText(`Deleted library "${library.name}".`);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('link', { name: library.name, exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: other.name, exact: true })).toBeVisible();
  await expect(page.locator('[data-tenant] h2[data-name]')).toHaveText(other.name);
  expect((await ok(owner.api.GET('/tenants'))).items.map((t) => t.id)).not.toContain(library.id);

  // Reloading does not bring it back from the hub's cache.
  await page.reload();
  await expect(page.getByRole('link', { name: other.name, exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: library.name, exact: true })).toHaveCount(0);
  await context.close();
});

test('Escape closes the dialog without deleting, and the focus goes back to the button', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const { page, context } = await signedInPage(browser, owner.subject);
  const article = await openLibrary(page, library);

  await article.locator('[data-tenant-tabs] > .tabs').getByRole('tab', { name: 'People' }).click();

  const open = article.getByRole('button', { name: 'Delete this library…' });
  const dialog = await openDeleteDialog(page, article);

  // The focus starts in the dialog, on the field for the name.
  await expect(dialog.getByLabel(`Type "${library.name}" to confirm`)).toBeFocused();
  await dialog.getByLabel(`Type "${library.name}" to confirm`).fill(library.name);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(open).toBeFocused();

  // Opened again, the name is asked for again.
  const again = await openDeleteDialog(page, article);

  await expect(again.getByLabel(`Type "${library.name}" to confirm`)).toHaveValue('');
  await expect(
    again.getByRole('button', { name: 'Delete this library', exact: true }),
  ).toBeDisabled();
  await again.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect((await ok(owner.api.GET('/tenants'))).items.map((t) => t.id)).toContain(library.id);
  await context.close();
});

test('an Organizer is told only an Owner can delete it, and has no button', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const orga = await addMember(owner, library.id, 'orga');
  const { page, context } = await signedInPage(browser, orga.subject);
  const article = await openLibrary(page, library);

  await article.locator('[data-tenant-tabs] > .tabs').getByRole('tab', { name: 'People' }).click();
  await expect(article.locator('[data-tenant-delete]')).toContainText(
    'Only an Owner can delete this library.',
  );
  await expect(article.getByRole('button', { name: /^Delete this library/ })).toHaveCount(0);
  await context.close();
});

test('an Owner whose account may not create libraries is told why there is no button', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  // An Owner by role, with an account that does not hold the platform permission.
  const second = await addMember(owner, library.id, 'owner');
  const { page, context } = await signedInPage(browser, second.subject);
  const article = await openLibrary(page, library);

  await article.locator('[data-tenant-tabs] > .tabs').getByRole('tab', { name: 'People' }).click();
  await expect(article.locator('[data-tenant-delete]')).toContainText(
    'deleting one also needs the permission to create libraries',
  );
  await expect(article.getByRole('button', { name: /^Delete this library/ })).toHaveCount(0);
  await context.close();
});

test('a repository other libraries draw on is refused in words, and goes once they stop', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Bestiary ${crypto.randomUUID().slice(0, 8)}`);
  const library = await newLibrary(owner.api);

  await publish(owner.api, repository.id);
  await invite(owner.api, repository.id, library.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await page.getByRole('tab', { name: 'People' }).click();

  const section = page.locator('[data-repository]');
  const dialog = await openDeleteDialog(page, section);
  const confirm = dialog.getByRole('button', { name: 'Delete this repository', exact: true });

  await dialog.getByLabel(`Type "${repository.name}" to confirm`).fill(repository.name);
  await confirm.click();

  // The API's refusal, in plain words, and nothing was deleted.
  await expect(dialog.locator('[data-dialog-error]')).toContainText(
    'Other libraries still draw on this repository',
  );
  await expect(dialog.locator('[data-dialog-error]')).not.toContainText('tenant');
  await expect(dialog).toBeVisible();
  expect((await ok(owner.api.GET('/tenants'))).items.map((t) => t.id)).toContain(repository.id);

  // Once no library holds it, the same dialog deletes it.
  await ok(
    owner.api.DELETE('/tenants/{tenant_id}/subscribers/{subscriber_tenant_id}', {
      params: { path: { tenant_id: repository.id, subscriber_tenant_id: library.id } },
    }),
  );
  await confirm.click();
  await expect(page.locator('[data-notice]')).toHaveText(
    `Deleted repository "${repository.name}".`,
  );
  expect((await ok(owner.api.GET('/tenants'))).items.map((t) => t.id)).not.toContain(repository.id);
  await context.close();
});
