import { expect, test } from '@playwright/test';

// Same deliberately minimal shape as home.spec.ts - proves the page
// resolves out of its loading state without a real Authgear session.
test('profile page loads and reaches a settled state when logged out', async ({ page }) => {
  await page.goto('/profile');
  await expect(page).toHaveTitle(/Lorenzo/);
  await expect(page.locator('#loading')).toBeHidden();
});
