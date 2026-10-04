import { expect, test } from '@playwright/test';
import { apiAs, ok } from '../../../inventory-web/tests/e2e/support/api';
import { signIn } from './support';

test('a refusal is a sentence, never the API body', async ({ page, context }) => {
  const subject = `hub-errors-${crypto.randomUUID()}`;
  const api = await apiAs(subject, ['tenant_creator']);
  await ok(api.GET('/me'));
  const taken = await ok(api.POST('/tenants', { body: { name: `Taken ${crypto.randomUUID()}` } }));
  await signIn(page, context, subject);
  await page.goto('/tenants');
  const form = page.locator('#create-tenant-container form');
  await expect(form).toBeVisible();

  // A 422 names the field.
  await form.getByPlaceholder('Name', { exact: true }).fill(`Library ${crypto.randomUUID()}`);
  await form.getByPlaceholder(/Slug/).fill('Not A Slug');
  await form.getByRole('button', { name: 'Create library' }).click();
  await expect(form.getByRole('status')).toContainText('Check what you entered: slug (');
  await expect(form.getByRole('status')).not.toContainText('{');

  // A 409 shows the API's own sentence.
  await form.getByPlaceholder(/Slug/).fill(taken.slug);
  await form.getByRole('button', { name: 'Create library' }).click();
  await expect(form.getByRole('status')).toContainText(/already in use|taken/i);
  await expect(form.getByRole('status')).not.toContainText('{');
});

test('Lorenzo being unreachable is said plainly', async ({ page, context }) => {
  const subject = `hub-offline-${crypto.randomUUID()}`;
  const api = await apiAs(subject);
  await ok(api.GET('/me'));
  await signIn(page, context, subject);
  await page.route('**/me', (route) => route.abort('connectionrefused'));
  await page.goto('/profile');
  await expect(page.locator('#load-error')).toHaveText(
    "Lorenzo couldn't be reached. Check your connection and try again.",
  );
});

test('an expired session says so, and "Log in" comes back to the same page', async ({
  page,
  context,
}) => {
  const subject = `hub-expired-${crypto.randomUUID()}`;
  const api = await apiAs(subject);
  await ok(api.GET('/me'));
  await signIn(page, context, subject);
  await page.route('**/me', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/problem+json',
      body: JSON.stringify({ type: 'unauthorized', title: 'Unauthorized', status: 401 }),
    }),
  );
  await page.goto('/profile');
  await expect(page.locator('#load-error')).toContainText(
    'Your session has expired. Log in again.',
  );
  await page.unroute('**/me');
  await page.locator('#load-error').getByRole('button', { name: 'Log in' }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.locator('#profile-form')).toBeVisible();
});
