import { expect, test } from '@playwright/test';
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

// ADR 0437, RFC 0051 H4: a repository built on another hides its entries from the libraries that copy
// it. The launcher sets PUBLIC_REPOSITORIES_ENABLED for this suite (playwright.real-api.config.ts).
// Every test works in names of its own (a tag in each), since the listing is the whole deployment's.

const WORDS_NEVER_ON_SCREEN = /tenant|grant|subscri|flatten|\bsource/i;

async function copyInto(api: Api, tenantId: string, repositoryId: string) {
  await ok(
    api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: tenantId, repository_id: repositoryId } },
      body: {},
    }),
  );
}

async function entriesOf(api: Api, tenantId: string): Promise<string[]> {
  const page = await ok(
    api.GET('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id: tenantId }, query: { size: 100 } },
    }),
  );

  return page.items.map((entry) => entry.name).sort();
}

// A is a protected repository with two items and a stat group; B is built on it (an invitation, a
// copy, and an item of its own); one Owner owns both.
async function world(prefix: string) {
  const owner = await newUser(`${prefix}-owner`, ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const a = await newRepository(owner.api, `Armoury ${tag}`);

  await addItem(owner.api, a.id, `Longsword ${tag}`, `longsword-${tag}`);
  await addItem(owner.api, a.id, `Dagger ${tag}`, `dagger-${tag}`);
  await addStatGroup(owner.api, a.id, 'Abilities', ['Strength']);
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/protected', {
      params: { path: { tenant_id: a.id } },
      body: { breaking: false, acknowledge_breaking: true, acknowledge_revokes: false },
    }),
  );

  const b = await newRepository(owner.api, `Bridge ${tag}`);

  await invite(owner.api, a.id, b.id);
  await copyInto(owner.api, b.id, a.id);
  await addItem(owner.api, b.id, `Bridge Blade ${tag}`);

  return { owner, tag, a, b };
}

test('an Owner keeps a protected repository separate and hidden, and a library that copies the repository holds its entries and does not see them', async ({
  browser,
}) => {
  test.slow();
  const { owner, tag, a, b } = await world('hide');
  const { page, context } = await signedInPage(browser, owner.subject);

  // The Built on tab offers the third choice, with what it does.
  await page.goto(`/repositories/?repository=${b.slug}`);
  await page.getByRole('tab', { name: 'Built on' }).click();

  const row = page.locator('[data-built-on-list] > li').filter({ hasText: a.name });

  await expect(row.getByRole('radio', { name: 'Keep separate and visible' })).toBeChecked();
  await expect(row.getByRole('radio', { name: 'Keep separate and hidden' })).not.toBeChecked();
  await row.getByRole('radio', { name: 'Keep separate and hidden' }).check();
  await expect(row.locator('[data-inclusion-status]')).toHaveText('Saved.');
  await expect(row).toContainText('does not see them');
  await expect(row).toContainText('not a secret');
  expect(await row.innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);

  // The repository goes public over it, with the choice carried by its release.
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: b.id } },
      body: {
        preview: 'public',
        breaking: false,
        acknowledge_breaking: true,
        accept_terms: true,
        summary: `A bridge ${tag}`,
      },
    }),
  );

  // A library copies it and holds A through it: it reads the entry of B and none of A's.
  const visitor = await newUser('hide-visitor', ['tenant_creator']);
  const library = await newLibrary(visitor.api, `Table ${tag}`);

  await copyInto(visitor.api, library.id, b.id);
  expect(await entriesOf(visitor.api, library.id)).toEqual([`Bridge Blade ${tag}`]);

  const guest = await signedInPage(browser, visitor.subject);

  await guest.page.goto(`/repositories/?tenant=${library.slug}`);
  await expect(guest.page.getByRole('listitem').filter({ hasText: b.name })).toBeVisible();
  expect(await guest.page.locator('main').innerText()).not.toContain('Longsword');
  expect(await guest.page.locator('main').innerText()).not.toContain('Dagger');

  // A releases a change: the library is told how many, never which, and takes it with the rest.
  await addItem(owner.api, a.id, `Pike ${tag}`, `pike-${tag}`);
  await publish(owner.api, a.id);

  const held = guest.page.getByRole('listitem').filter({ hasText: 'A protected repository' });

  await held.getByRole('link', { name: 'A protected repository' }).click();
  await guest.page.getByRole('link', { name: 'Check for updates' }).click();
  await expect(guest.page.locator('[data-updates-summary]')).toHaveText(
    '1 change to a hidden entry',
  );
  expect(await guest.page.locator('main').innerText()).not.toContain('Pike');
  await guest.page.getByRole('button', { name: 'Apply all clean' }).click();
  await expect(guest.page.locator('[data-bulk-receipt-text]')).toContainText(
    'take 1 change to a hidden entry',
  );
  await guest.page.getByRole('button', { name: 'Apply now' }).click();
  await expect(guest.page.locator('[data-updates-summary]')).toContainText('Up to date');
  expect(await entriesOf(visitor.api, library.id)).toEqual([`Bridge Blade ${tag}`]);
  expect(await guest.page.locator('main').innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);

  await context.close();
  await guest.context.close();
});

test('an Owner of a protected repository says it may not be hidden, and a repository built on it is left with show and include', async ({
  browser,
}) => {
  test.slow();
  const { owner, a } = await world('nohide');
  const ownerPage = await signedInPage(browser, owner.subject);

  await ownerPage.page.goto(`/repositories/?repository=${a.slug}`);
  await ownerPage.page.getByRole('tab', { name: 'Profile' }).click();

  const terms = ownerPage.page.locator('[data-terms-card]');

  await expect(terms.getByRole('checkbox', { name: 'May be hidden' })).toBeChecked();
  await terms.getByRole('checkbox', { name: 'May be hidden' }).uncheck();
  await expect(terms.locator('[data-terms-status]')).toHaveText('Saved.');
  await expect(terms.locator('[data-terms-hidden-line]')).toContainText('You did not allow it');
  // Neither preset says it now: it is not Open, and not Stay hidden.
  await expect(terms.getByRole('radio', { name: /^Open/ })).not.toBeChecked();
  await expect(terms.getByRole('radio', { name: /^Stay hidden/ })).not.toBeChecked();
  expect(await terms.innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);

  // Another Owner's repository built on it is not offered the choice, and is told why.
  const other = await newUser('nohide-other', ['tenant_creator']);
  const c = await newRepository(other.api, 'Other Bridge');

  await invite(owner.api, a.id, c.id);
  await copyInto(other.api, c.id, a.id);

  const otherPage = await signedInPage(browser, other.subject);

  await otherPage.page.goto(`/repositories/?repository=${c.slug}`);
  await otherPage.page.getByRole('tab', { name: 'Built on' }).click();

  const row = otherPage.page.locator('[data-built-on-list] > li').filter({ hasText: a.name });

  await expect(row.getByRole('radio', { name: 'Keep separate and hidden' })).toHaveCount(0);
  await expect(row.locator('[data-inclusion-not-offered]')).toContainText('You cannot keep');
  await expect(row.locator('[data-inclusion-not-offered]')).toContainText('separate and hidden');
  expect(await row.innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);

  await ownerPage.context.close();
  await otherPage.context.close();
});

test('on a phone, the three choices and the three switches are one column and each is big enough to press', async ({
  browser,
}) => {
  test.slow();
  const { owner, a, b } = await world('phone');
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  await page.goto(`/repositories/?repository=${b.slug}`);
  await page.getByRole('tab', { name: 'Built on' }).click();

  const row = page.locator('[data-built-on-list] > li').filter({ hasText: a.name });

  for (const name of [
    'Keep separate and visible',
    'Keep separate and hidden',
    'Include in this repository',
  ]) {
    const choice = row.getByRole('radio', { name });

    await expect(choice).toBeVisible();

    const box = await choice.locator('xpath=ancestor::label[1]').boundingBox();

    expect(box?.height).toBeGreaterThanOrEqual(44);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);

  await page.goto(`/repositories/?repository=${a.slug}`);
  await page.getByRole('tab', { name: 'Profile' }).click();

  const terms = page.locator('[data-terms-card]');

  for (const name of ['May be included', 'May be shown', 'May be hidden']) {
    const box = await terms
      .getByRole('checkbox', { name })
      .locator('xpath=ancestor::label[1]')
      .boundingBox();

    expect(box?.height).toBeGreaterThanOrEqual(44);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  await context.close();
});
