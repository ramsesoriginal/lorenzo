import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import { addItem, invite, newLibrary, newRepository, newUser, signedInPage } from './support';

// ADR 0299, RFC 0038 §6 items 4 to 6: what a repository's Owner learns of the libraries that copied
// it (a number, never a name), who a storefront says published it (the Owners' accounts), and the
// Report link. The launcher sets PUBLIC_REPOSITORIES_ENABLED and REPORT_ADDRESS for this suite
// (playwright.real-api.config.ts). Every test works in words of its own (a tag in each name).

const REPORT_ADDRESS = 'reports@example.test';

async function makePublic(api: Api, repositoryId: string, summary: string) {
  await ok(
    api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repositoryId } },
      body: {
        summary,
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
        accept_terms: true,
        label: '1.0',
      },
    }),
  );
}

async function copyInto(api: Api, tenantId: string, repositoryId: string) {
  await ok(
    api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: tenantId, repository_id: repositoryId } },
      body: {},
    }),
  );
}

// A public repository by an Owner with a name, one invited library, and a library of somebody else's
// that copied it by itself.
async function world() {
  const tag = crypto.randomUUID().slice(0, 8);
  const owner = await newUser('owner', ['tenant_creator']);
  const copier = await newUser('copier', ['tenant_creator']);

  await ok(owner.api.PATCH('/me', { body: { display_name: `Ada ${tag}` } }));

  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await addItem(owner.api, repository.id, 'Owlbear');

  const invited = await newLibrary(owner.api, `Invited ${tag}`);

  await invite(owner.api, repository.id, invited.id);
  await makePublic(owner.api, repository.id, `Every beast of ${tag}`);

  const secret = await newLibrary(copier.api, `Secret Society ${tag}`);

  await copyInto(copier.api, secret.id, repository.id);

  return { tag, owner, copier, repository, invited, secret };
}

const storefront = (page: Page) => page.locator('[data-storefront]');

test('Libraries using it names the invited and counts the ones that copied it by themselves', async ({
  browser,
}) => {
  const { owner, repository, invited, secret } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await page.getByRole('tab', { name: 'Libraries using it' }).click();

  const rows = page.locator('[data-using-list] > li');

  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText(invited.name);
  await expect(page.locator('[data-using-summary]')).toHaveText(
    '1 library or repository has an invitation or a copy. 0 of them have copied it.',
  );
  await expect(page.locator('[data-using-public]')).toHaveText(
    '1 library copied it by itself from Discover. Their names are not shown: you see how many, not which.',
  );

  // Not the library's name, link name or id anywhere on the tab, and not in the log either.
  await page.getByRole('tab', { name: 'Activity' }).click();
  await expect(page.locator('[data-activity-log] [data-entries]')).toBeVisible();
  await expect(page.locator('[data-activity-log]')).toContainText('repository.copied_publicly');
  const text = await page.locator('body').innerText();

  expect(text).not.toContain(secret.name);
  expect(text).not.toContain(secret.slug);
  expect(text).not.toContain(secret.id);

  const log = await ok(
    owner.api.GET('/tenants/{tenant_id}/activity-log', {
      params: { path: { tenant_id: repository.id } },
    }),
  );
  const copies = log.items.filter((entry) => entry.action === 'repository.copied_publicly');

  expect(copies).toHaveLength(1);
  expect(copies[0]?.actor_id).toBeNull();
  expect(copies[0]?.target_id).toBeNull();
  expect(JSON.stringify(log)).not.toContain(secret.id);
  await context.close();
});

test('Libraries using it says one number for several, and nothing when there are none', async ({
  browser,
}) => {
  const { owner, copier, repository, tag } = await world();
  const another = await newLibrary(copier.api, `Another ${tag}`);

  await copyInto(copier.api, another.id, repository.id);
  // Made before the page is opened: the hub keeps what it read of the Owner's repositories.
  const quiet = await newRepository(owner.api, `Quiet ${tag}`);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await page.getByRole('tab', { name: 'Libraries using it' }).click();
  await expect(page.locator('[data-using-public]')).toHaveText(
    '2 libraries copied it by themselves from Discover. Their names are not shown: you see how many, not which.',
  );

  // A repository that nobody copied by itself has no such line.
  await page.goto(`/studio/?repository=${quiet.slug}`);
  await expect(page.getByRole('heading', { name: quiet.name })).toBeVisible();
  await page.getByRole('tab', { name: 'Libraries using it' }).click();
  await expect(page.locator('[data-using-summary]')).toContainText('Nothing is using this');
  await expect(page.locator('[data-using-public]')).toBeHidden();
  await context.close();
});

test('a storefront and a result say who published it, from the Owners’ accounts', async ({
  browser,
}) => {
  const { tag, owner, copier, repository } = await world();

  // What the repository says of itself never changes it.
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: { credits: [{ name: 'Somebody Else', role: 'Publisher' }] },
    }),
  );

  const { page, context } = await signedInPage(browser, copier.subject);

  await page.goto(`/discover/?q=${tag}`);
  const card = page.locator('[data-results] > li');

  await expect(card).toHaveCount(1);
  await expect(card.locator('[data-published-by]')).toHaveText(`Published by Ada ${tag}`);

  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(storefront(page).getByRole('heading', { name: `Bestiary ${tag}` })).toBeVisible();
  await expect(storefront(page).locator('[data-published-by]')).toHaveText(
    `Published by Ada ${tag}`,
  );
  // The credits are a field of their own, and are shown as they were written.
  await expect(storefront(page).locator('[data-credits]')).toContainText('Somebody Else');
  await context.close();
});

test('the storefront has a plain Report link where a report address is set, and none where it is not', async ({
  browser,
}) => {
  const { tag, copier, repository } = await world();
  const { page, context } = await signedInPage(browser, copier.subject);

  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(storefront(page).getByRole('heading', { name: `Bestiary ${tag}` })).toBeVisible();

  const report = storefront(page).getByRole('link', { name: 'Report this repository' });

  await expect(report).toBeVisible();

  const href = (await report.getAttribute('href')) ?? '';

  expect(href.startsWith(`mailto:${REPORT_ADDRESS}?subject=`)).toBe(true);
  expect(decodeURIComponent(href)).toContain(`Bestiary ${tag}`);
  expect(decodeURIComponent(href)).toContain(repository.id);

  // Where the API says no address is set, there is no link.
  await page.route(`**/discover/repositories/${repository.id}`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();

    await route.fulfill({ response, json: { ...body, report_mailto: null } });
  });
  await page.reload();
  await expect(storefront(page).getByRole('heading', { name: `Bestiary ${tag}` })).toBeVisible();
  await expect(storefront(page).getByRole('link', { name: 'Report this repository' })).toBeHidden();
  await context.close();
});

test('at 375 pixels the storefront with its publisher and Report link fits and can be pressed', async ({
  browser,
}) => {
  const { tag, copier, repository } = await world();
  const { page, context } = await signedInPage(browser, copier.subject, {
    viewport: { width: 375, height: 812 },
  });

  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(storefront(page).locator('[data-published-by]')).toHaveText(
    `Published by Ada ${tag}`,
  );
  await expect(
    storefront(page).getByRole('link', { name: 'Report this repository' }),
  ).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );

  expect(overflow).toBeLessThanOrEqual(0);

  const height = await storefront(page)
    .getByRole('link', { name: 'Report this repository' })
    .evaluate((element) => Math.round(element.getBoundingClientRect().height));

  expect(height).toBeGreaterThanOrEqual(44);
  await context.close();
});
