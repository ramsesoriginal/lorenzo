import { expect, test } from '@playwright/test';

// Same deliberately minimal shape as the other page smoke tests.
test('repositories page loads and reaches a settled state when logged out', async ({ page }) => {
  await page.goto('/repositories');
  await expect(page).toHaveTitle(/Lorenzo/);
  await expect(page.locator('#loading')).toBeHidden();
});

// Studio became part of /repositories (ADR 0428); the old address sends people on with what they
// asked for, so bookmarks and links that were sent keep working.
test('/studio forwards to /repositories with its query', async ({ page }) => {
  await page.goto('/studio/?repository=core-rules');
  await expect(page).toHaveURL(/\/repositories\/\?repository=core-rules$/);
  await expect(page.locator('#loading')).toBeHidden();
});
