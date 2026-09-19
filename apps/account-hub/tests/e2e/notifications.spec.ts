import { expect, test } from '@playwright/test';

// Same deliberately minimal shape as home.spec.ts/profile.spec.ts.
test('notifications page loads and reaches a settled state when logged out', async ({ page }) => {
  await page.goto('/notifications');
  await expect(page).toHaveTitle(/Lorenzo/);
  await expect(page.locator('#loading')).toBeHidden();
});
