import { type BrowserContext, expect, type Page } from '@playwright/test';
import { AUTHGEAR_URL, SUBJECT_COOKIE } from '../../../inventory-web/tests/e2e/support/env';

/** Logs `page` in as `subject` through the fake Authgear's real PKCE round trip (ADR 0114). */
export async function signIn(page: Page, context: BrowserContext, subject: string): Promise<void> {
  await context.addCookies([{ name: SUBJECT_COOKIE, value: subject, url: AUTHGEAR_URL }]);
  await page.goto('/');
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.locator('#account-signed-in')).toBeVisible();
}
