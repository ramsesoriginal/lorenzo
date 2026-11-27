import { type Browser, expect, type Page, test } from '@playwright/test';
import { ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';
import { buildWorld } from './support/world.ts';

async function signedIn(browser: Browser, subject: string): Promise<Page> {
  const token = await refreshTokenFor(subject);
  const context = await browser.newContext({
    storageState: {
      cookies: [],
      origins: [{ origin: SITE_URL, localStorage: [{ name: REFRESH_TOKEN_KEY, value: token }] }],
    },
  });
  return context.newPage();
}

// A person's saved views of a list, kept in their account (ADR 0532).
test('the Events list keeps its filters as a named view, and sets itself by it again', async ({
  browser,
}) => {
  const world = await buildWorld();

  for (const name of ['Harvest moot', 'Winter fair', 'Spring moot']) {
    await ok(
      world.api.POST('/tenants/{tenant_id}/entities', {
        params: { path: { tenant_id: world.tenantId } },
        body: { name, kinds: ['event'], parents: [] },
      }),
    );
  }
  const page = await signedIn(browser, world.subject);

  await page.goto(`/events/?tenant=${world.tenantId}`);
  const views = page.getByRole('combobox', { name: 'Saved views' });

  await expect(page.getByRole('link', { name: /moot|fair/ })).toHaveCount(3);
  await page.getByLabel('Search Event names').fill('moot');
  await page.getByRole('button', { name: 'Find Events' }).click();
  await expect(page.getByRole('link', { name: /moot|fair/ })).toHaveCount(2);
  await page.getByRole('button', { name: 'Save this view…' }).click();
  await page.getByLabel('Name of the view').fill('Moots');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByText('Saved the view “Moots”.')).toBeVisible();

  // On another visit the list is whole again, and the view sets it.
  await page.goto(`/events/?tenant=${world.tenantId}`);
  await expect(page.getByRole('link', { name: /moot|fair/ })).toHaveCount(3);
  await views.selectOption({ label: 'Moots' });
  await expect(page.getByLabel('Search Event names')).toHaveValue('moot');
  await expect(page.getByRole('link', { name: /moot|fair/ })).toHaveCount(2);
  await page.getByRole('button', { name: 'Delete this view' }).click();
  await expect(page.getByText('Deleted the view “Moots”.')).toBeVisible();
  await page.context().close();
});
