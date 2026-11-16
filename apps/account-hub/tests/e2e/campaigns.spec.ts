import { expect, test } from '@playwright/test';

// /overview and /characters became one page (ADR 0179), and that page moved into the libraries
// (ADR 0428); the old addresses stay and send people on, so bookmarks and old links keep working.
for (const old of ['/overview', '/characters', '/campaigns']) {
  test(`${old} forwards to /tenants`, async ({ page }) => {
    await page.goto(old);
    await expect(page).toHaveURL(/\/tenants\/?$/);
    await expect(page.locator('#loading')).toBeHidden();
  });
}
