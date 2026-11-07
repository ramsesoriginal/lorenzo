import { expect, test } from '@playwright/test';
import { apiAs, ok } from '../../../inventory-web/tests/e2e/support/api';
import { newLibrary, newUser, openLibrary, signedInPage, signIn } from './support';

test('owner edits a slug, cancels, sees collision and invalid input, and cannot overwrite a stale edit', async ({
  page,
  context,
}) => {
  const subject = `hub-owner-${crypto.randomUUID()}`;
  const api = await apiAs(subject, ['tenant_creator']);
  await ok(api.GET('/me'));
  const tenant = await ok(api.POST('/tenants', { body: { name: `World ${crypto.randomUUID()}` } }));
  const taken = await ok(api.POST('/tenants', { body: { name: `Taken ${crypto.randomUUID()}` } }));
  await signIn(page, context, subject);
  const card = await openLibrary(page, tenant);
  await card.getByRole('tab', { name: 'Settings' }).click();
  const input = card.getByLabel('Library slug');
  const save = page.getByRole('button', { name: 'Save changes' });
  await expect(input).toHaveValue(tenant.slug);
  await input.fill('changed-but-cancelled');
  await page.getByRole('button', { name: 'Discard' }).click();
  await expect(input).toHaveValue(tenant.slug);
  expect(
    (await ok(api.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant.id } } })))
      .slug,
  ).toBe(tenant.slug);

  await input.fill('INVALID SLUG');
  await save.click();
  expect(await input.evaluate((el: HTMLInputElement) => el.checkValidity())).toBe(false);
  await input.fill(taken.slug);
  await save.click();
  await expect(card.locator('[data-form-status]')).toContainText('already in use');
  const slug = `renamed-${crypto.randomUUID()}`;
  await input.fill(slug);
  await save.click();
  await expect(card.locator('code[data-slug]')).toHaveText(slug);
  await expect(page.getByText('Saved', { exact: true })).toBeVisible();
  const renamed = await ok(
    api.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: tenant.id } } }),
  );
  expect(renamed.name).toBe(tenant.name);
  expect(renamed.slug).toBe(slug);

  await expect(input).toHaveValue(slug);
  await ok(
    api.PATCH('/tenants/{tenant_id}', {
      params: { path: { tenant_id: tenant.id } },
      body: { description: 'Changed in another tab' },
    }),
  );
  await input.fill(`stale-${crypto.randomUUID()}`);
  await save.click();
  await expect(card.locator('[data-form-status]')).toContainText('changed while you were editing');
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
      const page = await context.newPage();
      await signIn(page, context, subject);
      await page.goto('/tenants');
      await expect(page.locator('[data-tenants-panel]')).toContainText(tenant.name);
      await expect(page.locator('h2[data-name]')).toHaveText(tenant.name);
      if (role === 'orga') {
        await page.getByRole('tab', { name: 'Settings' }).click();
        const slug = `orga-${crypto.randomUUID()}`;
        await page.getByLabel('Library slug').fill(slug);
        await page.getByRole('button', { name: 'Save changes' }).click();
        await expect(page.locator('code[data-slug]')).toHaveText(slug);
      } else {
        await expect(page.getByLabel('Library slug')).toHaveCount(0);
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

test('an address for a library that is not theirs says the page is not available, and offers Home', async ({
  browser,
}) => {
  const stranger = await newUser('owner', ['tenant_creator']);
  const mine = await newLibrary(stranger.api, `Mine ${crypto.randomUUID().slice(0, 8)}`);
  const theirs = await newLibrary(
    (await newUser('other', ['tenant_creator'])).api,
    `Theirs ${crypto.randomUUID().slice(0, 8)}`,
  );

  const { page, context } = await signedInPage(browser, stranger.subject);

  await page.goto(`/tenants/?tenant=${theirs.slug}`);

  const unavailable = page.locator('[data-unavailable]');

  await expect(
    unavailable.getByRole('heading', { name: 'This page isn’t available' }),
  ).toBeVisible();
  await expect(unavailable).toContainText('you may not have access');
  await expect(unavailable.getByRole('link', { name: 'Go to Home' })).toHaveAttribute('href', '/');
  // Nothing of theirs is shown, and the address stays as it was asked.
  await expect(page.locator('[data-tenant]')).toBeHidden();
  await expect(page.getByText(theirs.name)).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`tenant=${theirs.slug}`));

  // Their own library is still one click away.
  await page.goto(`/tenants/?tenant=${mine.slug}`);
  await expect(page.locator('[data-unavailable]')).toBeHidden();
  await expect(page.locator('h2[data-name]')).toHaveText(mine.name);
  await context.close();
});
