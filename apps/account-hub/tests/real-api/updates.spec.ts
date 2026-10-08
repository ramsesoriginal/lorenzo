import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addItem,
  addStatGroup,
  invite,
  newLibrary,
  newRepository,
  newUser,
  publish,
  signedInPage,
} from './support';

async function copyInto(api: Api, libraryId: string, repositoryId: string) {
  await ok(
    api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: libraryId, repository_id: repositoryId } },
      body: {},
    }),
  );
}

async function rename(api: Api, tenantId: string, entityId: string, name: string) {
  await ok(
    api.PATCH('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { name },
    }),
  );
}

async function itemNames(api: Api, tenantId: string): Promise<string[]> {
  const page = await ok(
    api.GET('/tenants/{tenant_id}/items', { params: { path: { tenant_id: tenantId } } }),
  );

  return page.items.map((item) => item.title).sort();
}

async function itemNamed(api: Api, tenantId: string, name: string) {
  const page = await ok(
    api.GET('/tenants/{tenant_id}/items', { params: { path: { tenant_id: tenantId } } }),
  );
  const found = page.items.find((item) => item.title === name);

  if (!found) throw new Error(`No item called ${name} in ${tenantId}.`);

  return { id: found.entity_id };
}

// A library that has copied a repository, and then the repository moved on and the library did
// too: one entry the repository renamed and gave a parent (clean), one both renamed (a conflict),
// one it dropped, two it added (one of them with a link name the library already uses).
async function updatesWorld() {
  const owner = await newUser('updater', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const library = await newLibrary(owner.api, `Table ${tag}`);
  const repository = await newRepository(owner.api, `Armoury ${tag}`);
  const longsword = await addItem(owner.api, repository.id, 'Longsword', 'longsword');
  const shield = await addItem(owner.api, repository.id, 'Shield');
  const club = await addItem(owner.api, repository.id, 'Club');

  await addStatGroup(owner.api, repository.id, 'Combat', ['Damage']);
  await publish(owner.api, repository.id);
  await invite(owner.api, repository.id, library.id);
  await copyInto(owner.api, library.id, repository.id);

  // The library renames its copy of the longsword; the repository renames it too.
  await rename(
    owner.api,
    library.id,
    (await itemNamed(owner.api, library.id, 'Longsword')).id,
    'My blade',
  );
  await rename(owner.api, repository.id, longsword.entity_id, 'Longsword +1');

  // The repository renames the shield and gives it a parent that is new to the library.
  const weapon = await addItem(owner.api, repository.id, 'Weapon');

  await rename(owner.api, repository.id, shield.entity_id, 'Tower shield');
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/items/{entity_id}/prototypes', {
      params: { path: { tenant_id: repository.id, entity_id: shield.entity_id } },
      body: { prototype_ids: [weapon.entity_id] },
    }),
  );

  // It drops the club, and adds a buckler whose link name the library uses already.
  await ok(
    owner.api.DELETE('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { tenant_id: repository.id, entity_id: club.entity_id } },
    }),
  );
  await addItem(owner.api, repository.id, 'Buckler', 'buckler');
  await addItem(owner.api, library.id, 'My buckler', 'buckler');

  // What the repository did is released: a library takes a release, and apply all clean takes only
  // what a release holds (RFC 0037).
  await publish(owner.api, repository.id);

  return { owner, library, repository, longsword, tag };
}

function updatesAddress(library: { slug: string }, repository: { id: string }) {
  return `/repositories/?tenant=${library.slug}&repository=${repository.id}&updates=1`;
}

function row(page: Page, name: string) {
  return page.locator('[data-groups] > section > ul > li').filter({ hasText: name });
}

test('the inbox says what each copied repository has to offer, those with most to do first', async ({
  browser,
}) => {
  const { owner, library, repository, tag } = await updatesWorld();
  // A second repository, copied and left alone: nothing to update.
  const quiet = await newRepository(owner.api, `Quiet ${tag}`);

  await addItem(owner.api, quiet.id, 'Rope');
  await publish(owner.api, quiet.id);
  await invite(owner.api, quiet.id, library.id);
  await copyInto(owner.api, library.id, quiet.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/repositories/?tenant=${library.slug}`);
  await page.getByRole('link', { name: 'Check for updates' }).click();
  await expect(page).toHaveURL(/updates=1/);
  await expect(page.getByRole('heading', { name: `Updates for ${library.name}` })).toBeVisible();
  await expect(page.getByText('copied once and never updated').first()).toBeVisible();

  const rows = page.locator('[data-inbox-list] > li');

  await expect(rows).toHaveCount(2);
  // Each is checked, and says what it found in words; the one with the most to do is first.
  await expect(rows.first()).toContainText(repository.name);
  await expect(rows.first()).toContainText('1 changed, 2 new, 1 removed upstream, 1 conflict');
  await expect(rows.first()).toContainText('Updates');
  await expect(rows.last()).toContainText(quiet.name);
  await expect(rows.last()).toContainText('Up to date');

  // The row leads to the repository's updates.
  await rows.first().getByRole('link', { name: repository.name }).click();
  await expect(page).toHaveURL(/repository=/);
  await expect(
    page.getByRole('heading', { name: `Updates from ${repository.name}` }),
  ).toBeVisible();
  await context.close();
});

test('a repository’s updates, in groups, each change in words with names and never ids', async ({
  browser,
}) => {
  const { owner, library, repository } = await updatesWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(updatesAddress(library, repository));
  await expect(page.locator('[data-updates-summary]')).toHaveText(
    '1 changed, 2 new, 1 removed upstream, 1 conflict',
  );
  // What is not compared, that applying changes what players see, and that nothing is by itself.
  const notes = page.locator('[data-updates-notes]');

  await expect(notes).toContainText('copied once and never updated');
  await expect(notes).toContainText('Nothing is applied until you apply it.');
  await expect(notes).toContainText('changes what your players see');

  for (const heading of ['Conflicts (1)', 'Changed (1)', 'New (2)', 'Removed upstream (1)']) {
    await expect(page.getByRole('heading', { name: heading })).toBeVisible();
  }

  // A changed row: a field with what it was and what it is, and a parent added, by name.
  const shield = row(page, 'Shield');

  await expect(shield).toContainText('Name');
  await expect(shield.locator('dt', { hasText: 'Was' })).toBeVisible();
  await expect(shield).toContainText('Tower shield');
  await expect(shield).toContainText('Inherits from');
  await expect(shield.locator('dt', { hasText: 'Added' })).toBeVisible();
  await expect(shield).toContainText('Weapon');

  // A conflict: was, now and yours, and a choice for each, before it can be applied.
  const conflict = row(page, 'Longsword');

  await expect(conflict.locator('dd').filter({ hasText: /^Longsword$/ })).toBeVisible();
  await expect(conflict.locator('dd').filter({ hasText: /^Longsword \+1$/ })).toBeVisible();
  await expect(conflict.locator('dd').filter({ hasText: /^My blade$/ })).toBeVisible();
  await expect(conflict.getByRole('button', { name: 'Apply' })).toBeDisabled();
  await expect(conflict.getByText('Choose what to do about each conflict first.')).toBeVisible();

  // Nothing on the page is an id.
  expect(await page.locator('[data-updates-body]').innerText()).not.toMatch(
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|local:/,
  );
  await context.close();
});

test('a conflict is applied field by field: keep yours, or take the update', async ({
  browser,
}) => {
  const { owner, library, repository } = await updatesWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(updatesAddress(library, repository));

  const conflict = row(page, 'Longsword');

  await conflict.getByRole('radio', { name: 'Keep yours' }).check();
  await expect(conflict.getByRole('button', { name: 'Apply' })).toBeEnabled();
  await conflict.getByRole('button', { name: 'Apply' }).click();

  await expect(page.locator('[data-result-text]')).toHaveText('Applied 1 change.');
  // Yours stayed, and the row is gone.
  expect(await itemNames(owner.api, library.id)).toContain('My blade');
  await expect(page.getByRole('heading', { name: /^Conflicts/ })).toHaveCount(0);
  await context.close();
});

test('taking the update replaces the library’s own change', async ({ browser }) => {
  const { owner, library, repository } = await updatesWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(updatesAddress(library, repository));

  const conflict = row(page, 'Longsword');

  await conflict.getByRole('radio', { name: /Take the update/ }).check();
  await conflict.getByRole('button', { name: 'Apply' }).click();
  await expect(page.locator('[data-result-text]')).toHaveText('Applied 1 change.');
  expect(await itemNames(owner.api, library.id)).toContain('Longsword +1');
  await context.close();
});

test('apply all clean is checked first, shown as a receipt, and leaves the rest for a decision', async ({
  browser,
}) => {
  const { owner, library, repository } = await updatesWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(updatesAddress(library, repository));
  await expect(page.locator('[data-bulk-sentence]')).toHaveText(
    'Apply 1 change and 1 new. Left for you to decide: 1 conflict, 1 new with a name clash, 1 removed upstream.',
  );

  await page.getByRole('button', { name: 'Apply all clean' }).click();
  await expect(page.locator('[data-bulk-receipt-text]')).toHaveText(
    'Would apply 1 change, add 1 new. Nothing has changed yet.',
  );
  // Checked, not made.
  expect(await itemNames(owner.api, library.id)).not.toContain('Tower shield');

  // Cancel goes back; the check can be made again.
  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.getByRole('button', { name: 'Apply all clean' }).click();
  await page.getByRole('button', { name: 'Apply now' }).click();
  await expect(page.locator('[data-result-text]')).toHaveText('Applied 1 change, added 1 new.');

  const names = await itemNames(owner.api, library.id);

  expect(names).toContain('Tower shield');
  expect(names).toContain('Weapon');
  // What needs its own decision is still there, and nothing else is.
  await expect(page.getByRole('heading', { name: 'Conflicts (1)' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'New (1)' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Removed upstream (1)' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /^Changed/ })).toHaveCount(0);
  await context.close();
});

test('a new row that clashes with a name is a choice, as in the copy wizard', async ({
  browser,
}) => {
  const { owner, library, repository } = await updatesWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(updatesAddress(library, repository));

  const buckler = row(page, 'Buckler');

  await expect(
    buckler.getByText('Your library already has an entry with the link name “buckler”.'),
  ).toBeVisible();
  await expect(buckler.getByRole('button', { name: 'Add to your library' })).toBeDisabled();

  await buckler.getByRole('radio', { name: /Keep both/ }).check();
  await expect(buckler.getByLabel('New link name')).toHaveValue('buckler-2');
  await buckler.getByRole('button', { name: 'Add to your library' }).click();
  await expect(page.locator('[data-result-text]')).toHaveText('Added 1 new.');

  const entry = await ok(
    owner.api.GET('/tenants/{tenant_id}/entities/by-slug/{slug}', {
      params: { path: { tenant_id: library.id, slug: 'buckler-2' } },
    }),
  );

  expect(entry.name).toBe('Buckler');
  await context.close();
});

test('a row can be skipped and brought back, and a removed one detached', async ({ browser }) => {
  const { owner, library, repository } = await updatesWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(updatesAddress(library, repository));

  // Skipping puts it aside for now, out of what apply all clean takes.
  await row(page, 'Shield').getByRole('button', { name: 'Skip' }).click();
  await expect(page.getByText('Skipped for now (1)')).toBeVisible();
  await expect(page.locator('[data-bulk-sentence]')).toHaveText(
    'Apply 1 new. Left for you to decide: 1 conflict, 1 new with a name clash, 1 removed upstream.',
  );
  await page.getByText('Skipped for now (1)').click();
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(page.getByText(/Skipped for now/)).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Changed (1)' })).toBeVisible();

  // A row the repository dropped: the library's copy stays, and is no longer compared.
  const club = row(page, 'Club');

  await expect(club).toContainText('Yours stays as it is');
  await club.getByRole('button', { name: 'Detach' }).click();
  await expect(page.locator('[data-result-text]')).toHaveText('Detached 1.');
  expect(await itemNames(owner.api, library.id)).toContain('Club');
  await expect(page.getByRole('heading', { name: /^Removed upstream/ })).toHaveCount(0);
  await context.close();
});

test('the repository page offers a check for what was copied, and an address for what was not is ignored', async ({
  browser,
}) => {
  const { owner, library, repository, tag } = await updatesWorld();
  const fresh = await newRepository(owner.api, `Fresh ${tag}`);

  await publish(owner.api, fresh.id);
  await invite(owner.api, fresh.id, library.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  // The repository announces what it did: it is published again after the library's copy.
  await publish(owner.api, repository.id);
  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}`);
  await expect(page.getByText('Check for updates to see what changed.')).toBeVisible();
  await page.getByRole('link', { name: 'Check for updates' }).click();
  await expect(
    page.getByRole('heading', { name: `Updates from ${repository.name}` }),
  ).toBeVisible();

  // Not copied: there is nothing to update, so the page is the repository's own.
  await page.goto(updatesAddress(library, fresh));
  await expect(page.getByRole('heading', { name: fresh.name })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Check for updates' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: /^Updates from/ })).toBeHidden();
  await context.close();
});

test('on a phone, the updates are one column and everything pressed is big enough', async ({
  browser,
}) => {
  const { owner, library, repository } = await updatesWorld();
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  await page.goto(updatesAddress(library, repository));
  await expect(page.getByRole('heading', { name: 'Conflicts (1)' })).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );

  expect(overflow).toBeLessThanOrEqual(0);

  const heights = await page.evaluate(() =>
    [
      ...document.querySelectorAll<HTMLElement>(
        '[data-updates-view] button, [data-updates-view] .btn, [data-updates-view] .shelf-link, [data-updates-view] .field-row, [data-updates-view] .text-input, [data-updates-view] summary',
      ),
    ]
      .filter((element) => element.offsetParent !== null)
      .map((element) => Math.round(element.getBoundingClientRect().height)),
  );

  expect(heights.length).toBeGreaterThan(0);
  expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  await context.close();
});
