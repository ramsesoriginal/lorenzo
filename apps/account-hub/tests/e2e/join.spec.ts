import { expect, test } from '@playwright/test';

// Same deliberately minimal shape as the other page smoke tests, plus what is
// specific to a page that receives an invite token (ADR 0171): it settles
// without a login, says one thing for a missing or dead link, and takes the
// token out of the address bar.
const TOKEN = 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG';

test('join page with no link settles on one neutral message', async ({ page }) => {
  await page.goto('/join/');
  await expect(page).toHaveTitle(/Lorenzo/);
  await expect(page.locator('#loading')).toBeHidden();
  await expect(page.locator('[data-dead]')).toContainText("This link doesn't work any more.");
});

test('join page asks for no referrer, and removes the token from the address bar', async ({
  page,
}) => {
  // Whatever the API says about a link, the visitor is told the same thing.
  await page.route('**/invites/**', (route) =>
    route.fulfill({
      status: 404,
      contentType: 'application/problem+json',
      body: JSON.stringify({ type: 'not-found', title: 'Not Found', status: 404 }),
    }),
  );
  await page.goto(`/join/#${TOKEN}`);
  await expect(page.locator('#loading')).toBeHidden();
  await expect(page.locator('[data-dead]')).toContainText("This link doesn't work any more.");
  expect(page.url()).not.toContain(TOKEN);
  expect(new URL(page.url()).hash).toBe('');
  await expect(page.locator('meta[name="referrer"]')).toHaveAttribute('content', 'no-referrer');
  // A dead link is not kept for another try.
  expect(await page.evaluate(() => sessionStorage.getItem('lorenzo.invite'))).toBeNull();
});

const preview = (body: Record<string, unknown>) => ({
  campaign_name: null,
  picture_url: null,
  tenant_kind: null,
  role: null,
  ...body,
});

async function previewing(page: import('@playwright/test').Page, body: Record<string, unknown>) {
  await page.route('**/invites/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(preview(body)),
    }),
  );
  await page.goto(`/join/#${TOKEN}`);
  await expect(page.locator('#loading')).toBeHidden();
}

test('a role link says what it offers, in the three names, before anyone logs in', async ({
  page,
}) => {
  await previewing(page, {
    kind: 'tenant_role',
    name: 'A table',
    tenant_kind: 'play',
    role: 'author',
  });
  await expect(page.locator('[data-campaign]')).toHaveText('A table');
  await expect(page.locator('[data-offer]')).toHaveText(
    "You've been invited to join the library A table as an Author.",
  );
  await expect(page.locator('[data-paste]')).toBeHidden();
  expect(await page.locator('body').innerText()).not.toMatch(/\borga\b|tenant/i);
});

test('a link that shares a repository says so and does not show a library to anyone not logged in', async ({
  page,
}) => {
  await previewing(page, {
    kind: 'library_access',
    name: 'Faerûn',
    tenant_kind: 'repository',
    role: null,
  });
  await expect(page.locator('[data-offer]')).toContainText(
    'The repository Faerûn is being shared with a library of yours.',
  );
  await expect(page.locator('[data-share]')).toBeHidden();
});

test('with no link the page offers a box for a link or its code, and opens what is pasted', async ({
  page,
}) => {
  await page.route('**/invites/**', (route) =>
    route.fulfill({
      status: 404,
      contentType: 'application/problem+json',
      body: JSON.stringify({ type: 'not-found', title: 'Not Found', status: 404 }),
    }),
  );
  await page.goto('/join/');
  await expect(page.locator('[data-dead]')).toContainText("This link doesn't work any more.");
  const paste = page.locator('[data-paste]');
  await expect(paste).toBeVisible();

  await paste.getByLabel('Invite link or code').fill('not a code');
  await paste.getByRole('button', { name: 'Open invite' }).click();
  await expect(paste.getByRole('alert')).toContainText("doesn't look like an invite link or code");

  // The code alone is enough: the page goes on as a link opened would, and reads it the same.
  await paste.getByLabel('Invite link or code').fill(TOKEN);
  await paste.getByRole('button', { name: 'Open invite' }).click();
  // The page reloads on the new fragment and reads it like any link: the token leaves the address.
  await expect.poll(() => page.url()).not.toContain(TOKEN);
  await expect(page.locator('#loading')).toBeHidden();
});
