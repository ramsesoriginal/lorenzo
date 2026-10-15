import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import { addItem, newRepository, newUser, signedInPage } from './support';

// ADR 0301: releases of a public repository are held apart. Studio says the refusal in words, with
// the time the next release is possible in the reader's own time, and keeps the dialog open.
//
// The launcher sets the interval to 0 (playwright.real-api.config.ts), because the specs of this
// suite release the same repository again and again within seconds. The first test therefore has
// the API's refusal come from the browser's own network layer, in the shape the API writes it; the
// second runs against a launcher that has the interval at its default, and is for
// `E2E_RELEASE_COOLDOWN_SECONDS=300 pnpm exec playwright test --config
// playwright.real-api.config.ts tests/real-api/studio-release-cooldown.spec.ts`, which CI does too.

const dialog = (page: Page) => page.locator('[data-publish-dialog]');
const REAL = process.env.E2E_RELEASE_COOLDOWN_SECONDS === '300';

async function publicRepository() {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Bestiary ${crypto.randomUUID().slice(0, 8)}`);

  await addItem(owner.api, repository.id, 'Owlbear');
  // The flip's own release is not held back, and it is the newest as far as the next is concerned.
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repository.id } },
      body: {
        summary: 'Every monster there is',
        label: '1.0',
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
        accept_terms: true,
      },
    }),
  );

  return { owner, repository };
}

async function askForARelease(page: Page, slug: string) {
  await page.goto(`/studio/?repository=${slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
  await page.getByRole('button', { name: 'Publish a new release…' }).click();
  await expect(dialog(page).getByLabel('Label')).toBeVisible();
  await dialog(page).getByLabel('Label').fill('1.1');
  await dialog(page).getByRole('button', { name: 'Publish release' }).click();
}

test('a release inside the interval is refused in words, with the time the next is possible', async ({
  browser,
}) => {
  const { owner, repository } = await publicRepository();
  const { page, context } = await signedInPage(browser, owner.subject);
  const allowedAt = new Date(Date.now() + 240_000);

  // What the API answers inside the interval, as it writes it (apps/api, ADR 0301).
  await page.route(/\/tenants\/[^/]+\/published$/, async (route) => {
    if (route.request().method() !== 'PUT') return route.continue();

    return route.fulfill({
      status: 429,
      contentType: 'application/problem+json',
      headers: { 'access-control-allow-origin': '*', 'retry-after': '240' },
      body: JSON.stringify({
        type: 'release-cooldown',
        title: 'This repository released a moment ago',
        status: 429,
        detail: 'This repository can make its next release at 14:05 UTC.',
        allowed_at: allowedAt.toISOString(),
        interval_seconds: 300,
      }),
    });
  });

  await askForARelease(page, repository.slug);

  const said = dialog(page).locator('[data-dialog-error]');
  const time = allowedAt.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

  await expect(said).toContainText(`This repository can make its next release at ${time}.`);
  await expect(said).toContainText('Releases of a public repository are at least 5 minutes apart.');
  expect(await said.innerText()).not.toMatch(/tenant|grant|subscription|stable|frozen/i);
  // The dialog stays, to try again later, and nothing was published.
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page).getByRole('button', { name: 'Publish release' })).toBeEnabled();

  await context.close();
});

test('a public repository holds its releases five minutes apart, on a launcher that has the default', async ({
  browser,
}) => {
  test.skip(!REAL, 'Needs the launcher at its default: E2E_RELEASE_COOLDOWN_SECONDS=300.');

  const { owner, repository } = await publicRepository();
  const { page, context } = await signedInPage(browser, owner.subject);

  await askForARelease(page, repository.slug);

  const said = dialog(page).locator('[data-dialog-error]');

  await expect(said).toContainText('This repository can make its next release at');
  await expect(said).toContainText('Releases of a public repository are at least 5 minutes apart.');
  await expect(dialog(page)).toBeVisible();

  // It made no release: the one the flip made is the only one.
  await dialog(page).getByRole('button', { name: 'Cancel' }).click();
  await page.getByRole('tab', { name: 'Releases' }).click();
  await expect(page.getByRole('tabpanel').getByText('1.0', { exact: true })).toBeVisible();
  await expect(page.getByRole('tabpanel').getByText('1.1', { exact: true })).toHaveCount(0);

  await context.close();
});
