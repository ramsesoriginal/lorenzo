import { expect, test } from '@playwright/test';

// Same deliberately minimal shape as the other page smoke tests.
test('campaigns page loads and reaches a settled state when logged out', async ({ page }) => {
  await page.goto('/campaigns');
  await expect(page).toHaveTitle(/Lorenzo/);
  await expect(page.locator('#loading')).toBeHidden();
});

// /overview and /characters became one page (ADR 0179); the old addresses stay
// and send people on, so bookmarks and old links keep working.
for (const old of ['/overview', '/characters']) {
  test(`${old} forwards to /campaigns`, async ({ page }) => {
    await page.goto(old);
    await expect(page).toHaveURL(/\/campaigns\/?$/);
    await expect(page.locator('#loading')).toBeHidden();
  });
}
