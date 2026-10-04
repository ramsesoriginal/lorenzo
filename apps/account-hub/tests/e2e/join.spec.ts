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
  await expect(page.locator('#dead-link')).toContainText("This link doesn't work any more.");
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
  await expect(page.locator('#dead-link')).toContainText("This link doesn't work any more.");
  expect(page.url()).not.toContain(TOKEN);
  expect(new URL(page.url()).hash).toBe('');
  await expect(page.locator('meta[name="referrer"]')).toHaveAttribute('content', 'no-referrer');
  // A dead link is not kept for another try.
  expect(await page.evaluate(() => sessionStorage.getItem('lorenzo.invite'))).toBeNull();
});
