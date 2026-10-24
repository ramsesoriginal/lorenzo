import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { type Browser, expect, test } from '@playwright/test';
import { apiAs, ok, refreshTokenFor } from './support/api.ts';
import { API_URL, REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';

async function world(browser: Browser) {
  const subject = `writer-${randomUUID()}`;
  const owner = await apiAs(`owner-${randomUUID()}`, ['tenant_creator']);
  const tenant = await ok(
    owner.POST('/tenants', { body: { name: `Writing library ${randomUUID()}` } }),
  );
  const api = await apiAs(subject);
  const user = await ok(api.GET('/me'));
  await ok(
    owner.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: tenant.id } },
      body: { user_id: user.id, role: 'author' },
    }),
  );
  const context = await browser.newContext({
    storageState: {
      cookies: [],
      origins: [
        {
          origin: SITE_URL,
          localStorage: [{ name: REFRESH_TOKEN_KEY, value: await refreshTokenFor(subject) }],
        },
      ],
    },
  });
  const page = await context.newPage();
  await page.goto(`/?tenant=${tenant.id}`);
  await page.getByLabel('New draft title').fill('Across the water');
  await page.getByRole('button', { name: 'Start writing', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toBeVisible();
  return { api, owner, user, subject, tenant, page, context };
}

test('writing saves, preserves focus, and recovers an earlier saved revision', async ({
  browser,
}) => {
  const { page, context } = await world(browser);
  try {
    const text = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await text.fill('The river remembers.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await expect(text).toBeFocused();
    await text.fill('The river remembers every crossing.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.getByText('Saved revisions', { exact: true }).click();
    await page
      .locator('details')
      .filter({ has: page.getByText('Saved revisions', { exact: true }) })
      .getByRole('button')
      .first()
      .click();
    await expect(page.locator('pre')).toHaveText('The river remembers.');
    await page.getByRole('button', { name: 'Load this revision as a draft' }).click();
    await expect(text).toHaveValue('The river remembers.');
    await page.getByRole('button', { name: 'Save now', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.reload();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveValue(
      'The river remembers.',
    );
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    const audit = await new AxeBuilder({ page }).analyze();
    expect(audit.violations).toEqual([]);
    await page.getByRole('button', { name: 'Focus', exact: true }).click();
    await expect(page.locator('[data-site-header]')).toBeHidden();
    await page.getByRole('button', { name: 'Leave focus', exact: true }).click();
    await expect(page.locator('[data-site-header]')).toBeVisible();
  } finally {
    await context.close();
  }
});

test('unsent text survives reload and typing during a save is not overwritten', async ({
  browser,
}) => {
  const { page, context } = await world(browser);
  try {
    const text = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await page.route(`${API_URL}/tenants/**/payloads/*`, (route) =>
      route.request().method() === 'PATCH' ? route.abort() : route.continue(),
    );
    await text.fill('A draft kept in this browser.');
    await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
      'Use Save now to retry',
    );
    await page.reload();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveValue(
      'A draft kept in this browser.',
    );
    await page.unroute(`${API_URL}/tenants/**/payloads/*`);
    await page.getByRole('button', { name: 'Save now', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    let entered: () => void = () => {};
    const started = new Promise<void>((resolve) => {
      entered = resolve;
    });
    await page.route(`${API_URL}/tenants/**/payloads/*`, async (route) => {
      if (route.request().method() === 'PATCH') {
        entered();
        await held;
      }
      await route.continue();
    });
    await text.fill('First in flight.');
    await started;
    await text.fill('Still writing while it saves.');
    release();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await expect(text).toHaveValue('Still writing while it saves.');
    await page.reload();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveValue(
      'Still writing while it saves.',
    );
  } finally {
    await context.close();
  }
});

test('a concurrent edit stops autosave and keeps both versions for review', async ({ browser }) => {
  const { api, tenant, page, context } = await world(browser);
  try {
    const entry = new URL(page.url()).searchParams.get('entry') as string;
    const entity = await ok(
      api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenant.id, entity_id: entry } },
      }),
    );
    const payload = entity.information.find((i) => i.type === 'manuscript')?.payloads[0];
    if (!payload) throw new Error('No manuscript');
    await ok(
      api.PATCH('/tenants/{tenant_id}/payloads/{payload_id}', {
        params: {
          path: { tenant_id: tenant.id, payload_id: payload.id },
          header: { 'if-match': `W/"${payload.updated_at}"` },
        },
        body: { content: 'Written in another tab.' },
      }),
    );
    await page.getByRole('textbox', { name: 'Manuscript', exact: true }).fill('My unsent version.');
    await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
      'changed elsewhere',
    );
    await expect(page.locator('pre')).toHaveText('Written in another tab.');
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveValue(
      'My unsent version.',
    );
    await page.getByRole('button', { name: 'Continue with my draft' }).click();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.reload();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveValue(
      'My unsent version.',
    );
  } finally {
    await context.close();
  }
});

test('an unsent picture survives reload and saves with its text', async ({ browser }) => {
  const { page, context } = await world(browser);
  try {
    await page.route(`${API_URL}/tenants/**/information/*/payloads`, (route) => route.abort());
    const png = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
      'base64',
    );
    await page
      .locator('input[type=file]')
      .setInputFiles({ name: 'idea.png', mimeType: 'image/png', buffer: png });
    await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
      'Use Save now to retry',
    );
    await page.reload();
    await expect(page.getByRole('button', { name: 'Remove picture' })).toBeVisible();
    await page.unroute(`${API_URL}/tenants/**/information/*/payloads`);
    await page.getByRole('button', { name: 'Save now', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.reload();
    await expect(page.getByRole('button', { name: 'Remove picture' })).toBeVisible();
  } finally {
    await context.close();
  }
});

test('revoking the Author role hides the draft instead of restoring local text', async ({
  browser,
}) => {
  const { owner, user, tenant, page, context } = await world(browser);
  try {
    await page.route(`${API_URL}/tenants/**/payloads/*`, (route) =>
      route.request().method() === 'PATCH' ? route.abort() : route.continue(),
    );
    await page
      .getByRole('textbox', { name: 'Manuscript', exact: true })
      .fill('Private pending work.');
    await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
      'Use Save now to retry',
    );
    await ok(
      owner.DELETE('/tenants/{tenant_id}/memberships/{user_id}', {
        params: { path: { tenant_id: tenant.id, user_id: user.id } },
      }),
    );
    await page.reload();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveCount(0);
    await expect(page.locator('body')).not.toContainText('Private pending work.');
  } finally {
    await context.close();
  }
});

test('browser storage failure is visible while server saving remains possible', async ({
  browser,
}) => {
  const { page, context } = await world(browser);
  try {
    await page.addInitScript(() => {
      indexedDB.open = () => {
        throw new DOMException('No storage', 'QuotaExceededError');
      };
    });
    await page.reload();
    await expect(page.getByRole('alert')).toContainText('Browser recovery is unavailable');
    await page
      .getByRole('textbox', { name: 'Manuscript', exact: true })
      .fill('Still saved on the server.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.reload();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveValue(
      'Still saved on the server.',
    );
  } finally {
    await context.close();
  }
});

test('two open tabs retain independent unsent versions', async ({ browser }) => {
  const { page, context } = await world(browser);
  try {
    await context.route(`${API_URL}/tenants/**/payloads/*`, (route) =>
      route.request().method() === 'PATCH' ? route.abort() : route.continue(),
    );
    const second = await context.newPage();
    await second.goto(page.url());
    await expect(second.getByRole('textbox', { name: 'Manuscript', exact: true })).toBeVisible();
    await page.getByRole('textbox', { name: 'Manuscript', exact: true }).fill('First tab draft.');
    await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
      'Use Save now to retry',
    );
    await second
      .getByRole('textbox', { name: 'Manuscript', exact: true })
      .fill('Second tab draft.');
    await expect(second.getByRole('status', { name: 'Save status' })).toContainText(
      'Use Save now to retry',
    );
    await second.reload();
    await second.getByText('Details', { exact: true }).click();
    await expect(second.getByText('Other unsent drafts', { exact: true })).toBeVisible();
    const values = await second.evaluate(
      () =>
        new Promise<string[]>((resolve, reject) => {
          const open = indexedDB.open('lorenzo-writing-drafts');
          open.onerror = () => reject(open.error);
          open.onsuccess = () => {
            const db = open.result;
            const request = db.transaction('versions').objectStore('versions').getAll();
            request.onsuccess = () => {
              db.close();
              resolve(request.result.map((row) => row.draft.payloads[0].content));
            };
          };
        }),
    );
    expect(values).toContain('First tab draft.');
    expect(values).toContain('Second tab draft.');
  } finally {
    await context.close();
  }
});

test('changing accounts in the same browser does not load another author draft', async ({
  browser,
}) => {
  const { owner, tenant, page, context } = await world(browser);
  try {
    await page.route(`${API_URL}/tenants/**/payloads/*`, (route) =>
      route.request().method() === 'PATCH' ? route.abort() : route.continue(),
    );
    await page
      .getByRole('textbox', { name: 'Manuscript', exact: true })
      .fill('Only the first author typed this.');
    await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
      'Use Save now to retry',
    );
    const subject = `other-author-${randomUUID()}`;
    const other = await apiAs(subject);
    const user = await ok(other.GET('/me'));
    await ok(
      owner.POST('/tenants/{tenant_id}/memberships', {
        params: { path: { tenant_id: tenant.id } },
        body: { user_id: user.id, role: 'author' },
      }),
    );
    const token = await refreshTokenFor(subject);
    await page.evaluate(
      ({ key, token }) => {
        localStorage.clear();
        localStorage.setItem(key, token);
      },
      { key: REFRESH_TOKEN_KEY, token },
    );
    await page.reload();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveValue('');
    await expect(page.locator('body')).not.toContainText('Only the first author typed this.');
  } finally {
    await context.close();
  }
});

test('a long manuscript keeps the caret and saves without replacing the editor', async ({
  browser,
}, testInfo) => {
  const { api, tenant, page, context } = await world(browser);
  try {
    const text = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    const source = 'A long journey begins beside the river.\n'.repeat(7000);
    // Seed through the API: Chromium's insertText for this many lines also stalls in a
    // bare textarea. Exercise opening, typing and saving a book-length manuscript here.
    const entry = new URL(page.url()).searchParams.get('entry') as string;
    const entity = await ok(
      api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenant.id, entity_id: entry } },
      }),
    );
    const payload = entity.information.find((i) => i.type === 'manuscript')?.payloads[0];
    if (!payload) throw new Error('No manuscript');
    await ok(
      api.PATCH('/tenants/{tenant_id}/payloads/{payload_id}', {
        params: {
          path: { tenant_id: tenant.id, payload_id: payload.id },
          header: { 'if-match': `W/"${payload.updated_at}"` },
        },
        body: { content: source },
      }),
    );
    await page.reload();
    await expect(text).toHaveValue(source);
    await text.focus();
    await text.press('Control+End');
    await text.press('a');
    const before = await text.evaluate((el) => (el as HTMLTextAreaElement).selectionStart);
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved', {
      timeout: 15000,
    });
    await expect(text).toBeFocused();
    expect(await text.evaluate((el) => (el as HTMLTextAreaElement).selectionStart)).toBe(before);
    await page.screenshot({ path: testInfo.outputPath('writing-desktop.png'), fullPage: false });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: testInfo.outputPath('writing-phone.png'), fullPage: false });
  } finally {
    await context.close();
  }
});
