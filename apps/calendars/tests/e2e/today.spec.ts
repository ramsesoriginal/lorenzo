import { type Browser, expect, type Page, test } from '@playwright/test';
import { refreshTokenFor } from './support/api.ts';
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

// The date a calendar is at now, a field of the calendar (ADR 0530).
test('a writer makes a day today, the grid says so, and clearing it takes it away', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);

  await page.goto(
    `/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286&segment=segment-1`,
  );
  await page.getByRole('button', { name: '5 Rimsep 3286', exact: true }).click();
  await page.getByRole('button', { name: 'Make this day today' }).click();
  await expect(
    page.getByRole('button', { name: '5 Rimsep 3286, today', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Clear today' })).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole('button', { name: '5 Rimsep 3286, today', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: '5 Rimsep 3286, today', exact: true }).click();
  await page.getByRole('button', { name: 'Clear today' }).click();
  await expect(page.getByRole('button', { name: '5 Rimsep 3286', exact: true })).toBeVisible();
  await page.context().close();
});

test('the time filter offers This month once the calendar says what day it is', async ({
  browser,
}) => {
  const world = await buildWorld();
  const read = await world.api.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
    params: { path: { tenant_id: world.tenantId, entity_id: world.calendarId } },
  });

  await world.api.PUT('/tenants/{tenant_id}/calendars/{entity_id}/today', {
    params: {
      path: { tenant_id: world.tenantId, entity_id: world.calendarId },
      header: { 'if-match': read.response.headers.get('etag') },
    },
    body: { today: { year: 3286, segment: 'segment-1', day: 5 } },
  });
  const page = await signedIn(browser, world.subject);

  await page.goto(`/events/?tenant=${world.tenantId}`);
  const shortcut = page.getByRole('button', { name: 'This month' });

  await expect(shortcut).toBeVisible();
  await expect(page.getByRole('button', { name: 'Any time' })).toBeHidden();
  await shortcut.click();
  await expect(page.getByRole('button', { name: 'Any time' })).toBeVisible();
  await page.context().close();
});
