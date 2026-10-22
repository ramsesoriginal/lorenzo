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

for (const phone of [false, true])
  test(`clock dates and conflicting drafts ${phone ? 'on phone' : 'on desktop'}`, async ({
    browser,
  }) => {
    const w = await buildWorld();
    const page = await signedIn(browser, w.subject);
    if (phone) await page.setViewportSize({ width: 390, height: 844 });
    try {
      await page.goto(`/clocks/?tenant=${w.tenantId}`);
      await page.getByText('Create a clock', { exact: true }).click();
      await page.getByLabel('Clock name', { exact: true }).fill('Mainland');
      await page.getByLabel('Everyone in this library can see this clock').check();
      await page.getByRole('button', { name: 'Create clock', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Mainland', exact: true })).toBeVisible();
      await page.getByText('Clock and calendar reckonings', { exact: true }).click();
      await page.getByLabel('Calendar year', { exact: true }).fill('3286');
      await page.getByLabel('Clock reading at the start of this date').fill('17');
      await page.getByRole('button', { name: 'Save reckoning', exact: true }).click();
      await expect(
        page.getByText('Reckoning saved. Entered Event readings were kept.', { exact: true }),
      ).toBeVisible();
      const clocks = await ok(
        w.api.GET('/tenants/{tenant_id}/clocks', { params: { path: { tenant_id: w.tenantId } } }),
      );
      const clock = clocks.find((c) => c.name === 'Mainland');
      if (!clock) throw new Error('Clock was not created');
      const event = await ok(
        w.api.POST('/tenants/{tenant_id}/entities', {
          params: { path: { tenant_id: w.tenantId } },
          body: { name: 'Arrival at the wreck', kinds: ['event'], parents: [] },
        }),
      );
      await page.goto(`/entry/?tenant=${w.tenantId}&id=${event.id}`);
      await page.getByText('Clock readings', { exact: true }).click();
      await page.getByText('Enter a calendar date', { exact: true }).click();
      await page.getByLabel('Calendar year', { exact: true }).fill('3286');
      await page.getByRole('combobox', { name: /^Month or festival/ }).selectOption('segment-6');
      await page.getByLabel('Calendar day', { exact: true }).fill('16');
      await page.getByRole('button', { name: 'Use this day', exact: true }).click();
      await expect(page.getByLabel('Reading start', { exact: true })).toHaveValue('142');
      await page.getByRole('button', { name: 'Save reading', exact: true }).click();
      await expect(
        page.getByText('Mainland: [142, 143) — Entered. Private.', { exact: true }),
      ).toBeVisible();
      await page.getByLabel('Reading start', { exact: true }).fill('23');
      await page
        .getByLabel('Reading end (leave empty for an exact point)', { exact: true })
        .fill('');
      const path = { tenant_id: w.tenantId, event_id: event.id };
      const current = await w.api.GET('/tenants/{tenant_id}/events/{event_id}/clock-readings', {
        params: { path },
      });
      await ok(
        w.api.PUT('/tenants/{tenant_id}/events/{event_id}/clock-readings/{clock_id}', {
          params: {
            path: { ...path, clock_id: clock.entity_id },
            header: { 'if-match': current.response.headers.get('etag') ?? '' },
          },
          body: {
            reading: { lo: '19', hi: '19', lo_inclusive: true, hi_inclusive: true },
            is_shared: false,
          },
        }),
      );
      await page.getByLabel('Include the end', { exact: true }).check();
      await page.getByRole('button', { name: 'Save reading', exact: true }).click();
      await expect(
        page.getByText(/Your draft is kept. Refresh saved records to review changes/),
      ).toBeVisible();
      await expect(page.getByLabel('Reading start', { exact: true })).toHaveValue('23');
      await page.getByRole('button', { name: 'Refresh saved records', exact: true }).click();
      await expect(
        page.getByText('Mainland: 19 — Entered. Private.', { exact: true }),
      ).toBeVisible();
      await expect(page.getByLabel('Reading start', { exact: true })).toHaveValue('23');
      await page.getByRole('button', { name: 'Save reading', exact: true }).click();
      await expect(
        page.getByText('Mainland: 23 — Entered. Private.', { exact: true }),
      ).toBeVisible();
      await page.screenshot({
        path: `test-results/clocks-${phone ? 'phone' : 'desktop'}.png`,
        fullPage: true,
      });
    } finally {
      await page
        .context()
        .close()
        .catch(() => {});
    }
  });
