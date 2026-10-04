import { expect, test } from '@playwright/test';
import { apiAs, ok } from '../../../inventory-web/tests/e2e/support/api';
import { AUTHGEAR_URL, SUBJECT_COOKIE } from '../../../inventory-web/tests/e2e/support/env';

test('owner edits a slug, cancels, sees collision and invalid input, and cannot overwrite a stale edit', async ({
  page,
  context,
}) => {
  const subject = `hub-owner-${crypto.randomUUID()}`;
  const api = await apiAs(subject, ['tenant_creator']);
  await ok(api.GET('/me'));
  const tenant = await ok(api.POST('/tenants', { body: { name: `World ${crypto.randomUUID()}` } }));
  const taken = await ok(api.POST('/tenants', { body: { name: `Taken ${crypto.randomUUID()}` } }));
  await context.addCookies([{ name: SUBJECT_COOKIE, value: subject, url: AUTHGEAR_URL }]);
  await page.goto('/');
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.locator('#account-signed-in')).toBeVisible();
  await page.goto('/tenants');
  const card = page
    .locator('#tenant-list > li')
    .filter({ has: page.getByRole('heading', { name: `${tenant.name} owner`, exact: true }) });
  await card.getByRole('button', { name: 'Edit library' }).click();
  const input = card.getByLabel('Library slug');
  await expect(input).toHaveValue(tenant.slug);
  await input.fill('changed-but-cancelled');
  await card.getByRole('button', { name: 'Cancel', exact: true }).click();
  expect(
    (await ok(api.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant.id } } })))
      .slug,
  ).toBe(tenant.slug);

  await card.getByRole('button', { name: 'Edit library' }).click();
  await input.fill('INVALID SLUG');
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  expect(await input.evaluate((el: HTMLInputElement) => el.checkValidity())).toBe(false);
  await input.fill(taken.slug);
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(card.locator('.tenant-details')).toContainText('already in use');
  const slug = `renamed-${crypto.randomUUID()}`;
  await input.fill(slug);
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(card.locator('.tenant-details-value')).toHaveText(`Slug: ${slug}`);
  await expect(card.locator('.tenant-details')).toContainText('Saved.');
  const renamed = await ok(
    api.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant.id } } }),
  );
  expect(renamed.name).toBe(tenant.name);
  expect(renamed.slug).toBe(slug);

  await card.getByRole('button', { name: 'Edit library' }).click();
  await expect(input).toHaveValue(slug);
  await ok(
    api.PATCH('/tenants/{tenant_id}', {
      params: { path: { tenant_id: tenant.id } },
      body: { description: 'Changed in another tab' },
    }),
  );
  await input.fill(`stale-${crypto.randomUUID()}`);
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(card.locator('.tenant-details')).toContainText('changed while you were editing');
  await expect(card.getByRole('button', { name: 'Save', exact: true })).toBeDisabled();
  expect(
    (await ok(api.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant.id } } })))
      .slug,
  ).toBe(slug);
});

test('organizers can edit, campaign participants cannot', async ({ browser }) => {
  const owner = await apiAs(`hub-owner-${crypto.randomUUID()}`, ['tenant_creator']);
  await ok(owner.GET('/me'));
  const tenant = await ok(
    owner.POST('/tenants', { body: { name: `Roles ${crypto.randomUUID()}` } }),
  );
  const campaign = await ok(
    owner.POST('/tenants/{tenant_id}/campaigns', {
      params: { path: { tenant_id: tenant.id } },
      body: {
        name: 'Campaign',
        slug: 'campaign',
        description: '',
        game_system: 'test',
        secret: false,
      },
    }),
  );
  for (const role of ['orga', 'participant'] as const) {
    const subject = `hub-${role}-${crypto.randomUUID()}`;
    const api = await apiAs(subject);
    const user = await ok(api.GET('/me'));
    if (role === 'orga') {
      await ok(
        owner.POST('/tenants/{tenant_id}/memberships', {
          params: { path: { tenant_id: tenant.id } },
          body: { user_id: user.id, role },
        }),
      );
    } else {
      await ok(
        owner.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
          params: { path: { tenant_id: tenant.id, campaign_id: campaign.id } },
          body: { user_id: user.id },
        }),
      );
    }
    const context = await browser.newContext();
    try {
      await context.addCookies([{ name: SUBJECT_COOKIE, value: subject, url: AUTHGEAR_URL }]);
      const page = await context.newPage();
      await page.goto('/');
      await page.getByRole('button', { name: 'Log in' }).click();
      await expect(page.locator('#account-signed-in')).toBeVisible();
      await page.goto('/tenants');
      await expect(page.locator('#tenant-list')).toContainText(tenant.name);
      if (role === 'orga') {
        await page.getByRole('button', { name: 'Edit library' }).click();
        const slug = `orga-${crypto.randomUUID()}`;
        await page.getByLabel('Library slug').fill(slug);
        await page.getByRole('button', { name: 'Save', exact: true }).click();
        await expect(page.locator('.tenant-details-value')).toHaveText(`Slug: ${slug}`);
      } else {
        await expect(page.getByRole('button', { name: 'Edit library' })).toHaveCount(0);
        const refused = await api.PATCH('/tenants/{tenant_id}', {
          params: { path: { tenant_id: tenant.id } },
          body: { slug: 'forbidden' },
        });
        expect(refused.response.status).toBe(404);
      }
    } finally {
      await context.close();
    }
  }
});
