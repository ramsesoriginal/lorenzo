import { expect, test } from '@playwright/test';

// A deliberately minimal first slice: proves the page renders and the
// Authgear-aware script runs, without requiring a real Authgear session
// (that needs the manual client registration ADR 0071 calls out). Login/
// notification/tenant flows get their own e2e tests in later slices.
test('home page loads and reaches a settled auth state', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Lorenzo/);
  await expect(page.getByRole('link', { name: 'Lorenzo' }).first()).toBeVisible();

  // Either state is a valid outcome depending on whether PUBLIC_AUTHGEAR_*
  // is configured for this run - the point is the loading state resolves,
  // not which branch it resolves to.
  await expect(page.locator('#account-loading')).toBeHidden();
});
