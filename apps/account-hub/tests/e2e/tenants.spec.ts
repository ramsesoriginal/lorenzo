import { expect, test } from '@playwright/test';

// Same deliberately minimal shape as the other page smoke tests.
test('tenants page loads and reaches a settled state when logged out', async ({ page }) => {
  await page.goto('/tenants');
  await expect(page).toHaveTitle(/Lorenzo/);
  await expect(page.locator('#loading')).toBeHidden();
});
