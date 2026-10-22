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
  test(`clock relationships and permitted derived readings ${phone ? 'on phone' : 'on desktop'}`, async ({
    browser,
  }) => {
    test.slow();
    const w = await buildWorld();
    const staff = await signedIn(browser, w.subject);
    const reader = await signedIn(browser, w.readerSubject);
    if (phone) {
      await staff.setViewportSize({ width: 390, height: 844 });
      await reader.setViewportSize({ width: 390, height: 844 });
    }
    const path = { tenant_id: w.tenantId };
    try {
      const mainland = await ok(
        w.api.POST('/tenants/{tenant_id}/clocks', {
          params: { path },
          body: { name: 'Mainland', ticking: true, is_public: true },
        }),
      );
      const fey = await ok(
        w.api.POST('/tenants/{tenant_id}/clocks', {
          params: { path },
          body: { name: 'Fey', ticking: true, is_public: true },
        }),
      );
      await staff.goto(`/entry/?tenant=${w.tenantId}&id=${fey.entity_id}`);
      await staff.getByText('Clock relationships and conversion', { exact: true }).click();
      await staff
        .getByRole('combobox', { name: /^Reference clock/ })
        .selectOption(mainland.entity_id);
      await staff.getByLabel('Days on this clock per reference day', { exact: true }).fill('2');
      await staff.getByLabel('Anchor the readings', { exact: true }).check();
      await staff.getByLabel('This clock reads', { exact: true }).fill('34');
      await staff.getByLabel('Reference clock reads', { exact: true }).fill('17');
      await staff
        .getByLabel('Reference reading or duration to preview', { exact: true })
        .fill('20');
      await staff.getByRole('button', { name: 'Preview relationship', exact: true }).click();
      await expect(
        staff.getByText('Fey: 40 (reading). Preview only.', { exact: true }),
      ).toBeVisible();
      const relationPath = { ...path, clock_id: fey.entity_id };
      expect(
        (
          await ok(
            w.api.GET('/tenants/{tenant_id}/clocks/{clock_id}/relationships', {
              params: { path: relationPath },
            }),
          )
        ).items,
      ).toHaveLength(0);
      await staff.getByRole('button', { name: 'Save relationship', exact: true }).click();
      await expect(
        staff.getByText('Fey: 2 days per day on Mainland. Private.', { exact: true }),
      ).toBeVisible();
      const event = await ok(
        w.api.POST('/tenants/{tenant_id}/entities', {
          params: { path },
          body: {
            name: 'Return from the Fey',
            kinds: ['event'],
            parents: [],
            visibility: 'library',
          },
        }),
      );
      const eventPath = { ...path, event_id: event.id };
      const current = await w.api.GET('/tenants/{tenant_id}/events/{event_id}/clock-readings', {
        params: { path: eventPath },
      });
      await ok(
        w.api.PUT('/tenants/{tenant_id}/events/{event_id}/clock-readings/{clock_id}', {
          params: {
            path: { ...eventPath, clock_id: fey.entity_id },
            header: { 'if-match': current.response.headers.get('etag') ?? '' },
          },
          body: {
            reading: { lo: '40', hi: '40', lo_inclusive: true, hi_inclusive: true },
            is_shared: true,
          },
        }),
      );
      await reader.goto(`/entry/?tenant=${w.tenantId}&id=${event.id}`);
      await reader.getByText('Read this Event on another clock', { exact: true }).click();
      await reader
        .getByRole('combobox', { name: /^Read on clock/ })
        .selectOption(mainland.entity_id);
      await reader.getByRole('button', { name: 'Show clock reading', exact: true }).click();
      await expect(
        reader.getByRole('heading', { name: 'Not reckoned', exact: true }),
      ).toBeVisible();
      await staff
        .getByLabel('Share relationship with readers of both clocks', { exact: true })
        .check();
      await staff.getByRole('button', { name: 'Save relationship', exact: true }).click();
      await expect(
        staff.getByText('Fey: 2 days per day on Mainland. Shared.', { exact: true }),
      ).toBeVisible();
      await reader.getByRole('button', { name: 'Show clock reading', exact: true }).click();
      await expect(reader.getByRole('heading', { name: 'Derived', exact: true })).toBeVisible();
      await expect(reader.getByText('20', { exact: true })).toBeVisible();
      expect(
        (
          await ok(
            w.api.GET('/tenants/{tenant_id}/events/{event_id}/clock-readings', {
              params: { path: eventPath },
            }),
          )
        ).items,
      ).toHaveLength(1);
      await expect(reader.getByRole('button', { name: 'Save reading', exact: true })).toHaveCount(
        0,
      );
      await staff.getByLabel('Days on this clock per reference day', { exact: true }).fill('3');
      const saved = await w.api.GET('/tenants/{tenant_id}/clocks/{clock_id}/relationships', {
        params: { path: relationPath },
      });
      await ok(
        w.api.PUT('/tenants/{tenant_id}/clocks/{clock_id}/relationships/{reference_id}', {
          params: {
            path: { ...relationPath, reference_id: mainland.entity_id },
            header: { 'if-match': saved.response.headers.get('etag') ?? '' },
          },
          body: { ratio: '4', clock_anchor: '34', reference_anchor: '17', is_shared: true },
        }),
      );
      await staff.getByRole('button', { name: 'Save relationship', exact: true }).click();
      await expect(staff.getByText(/Your draft is kept. Refresh saved records/)).toBeVisible();
      await staff.getByRole('button', { name: 'Refresh saved relationships', exact: true }).click();
      await expect(
        staff.getByText('Fey: 4 days per day on Mainland. Shared.', { exact: true }),
      ).toBeVisible();
      await expect(
        staff.getByLabel('Days on this clock per reference day', { exact: true }),
      ).toHaveValue('3');
      await staff.getByRole('button', { name: 'Save relationship', exact: true }).click();
      await expect(
        staff.getByText('Fey: 3 days per day on Mainland. Shared.', { exact: true }),
      ).toBeVisible();
      await reader.getByRole('button', { name: 'Show clock reading', exact: true }).click();
      await expect(reader.getByText('19', { exact: true })).toBeVisible();
      await reader.screenshot({
        path: `test-results/clock-ratios-${phone ? 'phone' : 'desktop'}.png`,
        fullPage: true,
      });
    } finally {
      await staff
        .context()
        .close()
        .catch(() => {});
      await reader
        .context()
        .close()
        .catch(() => {});
    }
  });
