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
  // Initial sign-in, entry authorization and bundle creation can exceed five seconds on a cold API.
  await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toBeVisible({
    timeout: 15000,
  });
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

test('a Book has nested Chapters, mixed reading order and independent Editions', async ({
  browser,
}) => {
  test.setTimeout(90000);
  const { page, context, tenant } = await world(browser);
  try {
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('Journeys');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await manuscript.fill('Before departure.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const firstEdition = new URL(page.url()).searchParams.get('entry');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByLabel('New chapter title').fill('Departure');
    await page.getByRole('button', { name: 'Add chapter', exact: true }).click();
    await page.getByRole('link', { name: 'Departure', exact: true }).click();
    await manuscript.fill('The boat left.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByLabel('New chapter title').fill('At the shore');
    await page.getByRole('button', { name: 'Add chapter', exact: true }).click();
    await page.getByRole('link', { name: 'At the shore', exact: true }).click();
    await manuscript.fill('A light remained.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${firstEdition}&view=outline`);
    await page.getByRole('button', { name: 'Up: Departure', exact: true }).click();
    await expect(page.locator('ol > li').first()).toContainText('Departure');
    // Removing a Chapter preserves its subtree, which can be found and placed again.
    await page.getByRole('button', { name: 'Remove from outline', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Departure', exact: true })).toHaveCount(0);
    await page.getByText('Place an existing Chapter', { exact: true }).click();
    await page.getByLabel('Find a Chapter', { exact: true }).fill('Departure');
    await page.getByRole('button', { name: 'Find Chapters', exact: true }).click();
    await page.getByRole('button', { name: 'Departure', exact: true }).click();
    await page.getByRole('button', { name: 'Up: Departure', exact: true }).click();
    await expect(page.locator('ol > li').first()).toContainText('Departure');
    await page.screenshot({ path: test.info().outputPath('outline-desktop.png'), fullPage: true });
    await page.getByRole('link', { name: 'Read', exact: true }).click();
    await expect(page.locator('article')).toHaveText(
      /Departure.*The boat left.*At the shore.*A light remained.*Before departure\./s,
    );
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByText('Editions', { exact: true }).click();
    await page.getByLabel('New edition title').fill('Revised edition');
    await page.getByRole('button', { name: 'Create independent edition', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Revised edition', exact: true })).toBeVisible();
    await page.getByRole('link', { name: 'Departure', exact: true }).click();
    await expect(manuscript).toHaveValue('The boat left.');
    await manuscript.fill('The boat waited.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${firstEdition}&view=read`);
    await expect(page.locator('article')).toContainText('The boat left.');
    await expect(page.locator('article')).not.toContainText('The boat waited.');
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: test.info().outputPath('reading-phone.png'), fullPage: true });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  } finally {
    await context.close();
  }
});

test('reusing a Scene keeps tellings independent and supports a viewpoint biography', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context, tenant } = await world(browser);
  try {
    const text = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await text.fill('The river remembers.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const sceneId = new URL(page.url()).searchParams.get('entry');
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('biography');
    await page.getByLabel('New draft title').fill('Ferryman');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    await text.fill('He knows every crossing.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}`);
    await expect(page.getByRole('link', { name: 'Ferryman', exact: true })).toBeVisible();
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('River book');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'River book', exact: true })).toBeVisible();
    const edition = new URL(page.url()).searchParams.get('entry');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    for (let n = 0; n < 2; n++) {
      await page.getByText('Use a Scene', { exact: true }).click();
      await page.getByLabel('Find a Scene', { exact: true }).fill('Across the water');
      await page.getByRole('button', { name: 'Find Scenes', exact: true }).click();
      await page.getByRole('button', { name: 'Across the water', exact: true }).click();
      await expect(page.getByRole('link', { name: 'Across the water', exact: true })).toHaveCount(
        n + 1,
      );
    }
    await page.getByRole('link', { name: 'Across the water', exact: true }).first().click();
    await expect(page.locator('article')).toContainText('The river remembers.');
    await page.getByText('Details', { exact: true }).click();
    await page.getByText('Viewpoint', { exact: true }).click();
    await page.getByLabel('Viewpoint', { exact: true }).fill('Ferryman');
    await page.getByRole('button', { name: 'Find viewpoint', exact: true }).click();
    await page.getByRole('button', { name: 'Ferryman', exact: true }).click();
    await expect(page.getByText('Viewpoint: Ferryman', { exact: true })).toBeVisible();
    await page.screenshot({ path: test.info().outputPath('telling-desktop.png'), fullPage: true });
    await page.getByRole('button', { name: 'Make independent', exact: true }).click();
    await expect(text).toHaveValue('The river remembers.');
    await text.fill('The ferryman remembers.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=read`);
    await expect(page.locator('article')).toHaveText(
      /The ferryman remembers.*The river remembers/s,
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: test.info().outputPath('tellings-phone.png'), fullPage: true });
    await page.goto(`/?tenant=${tenant.id}&entry=${sceneId}`);
    await expect(text).toHaveValue('The river remembers.');
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  } finally {
    await context.close();
  }
});

test('an invited reviewer reads one Edition, writes private notes and loses access on revocation', async ({
  browser,
}) => {
  test.setTimeout(150000);
  const { page, context, tenant } = await world(browser);
  const subject = `reviewer-${randomUUID()}`;
  const reviewer = await apiAs(subject);
  await ok(reviewer.GET('/me'));
  const reviewContext = await browser.newContext({
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
  try {
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('A review copy');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'A review copy', exact: true })).toBeVisible();
    await page
      .getByRole('textbox', { name: 'Manuscript', exact: true })
      .fill('The river remembers the old bridge.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.getByText('Details', { exact: true }).click();
    await page.getByRole('link', { name: 'Review and reviewers', exact: true }).click();
    await expect(page.locator('article')).toContainText('The river remembers the old bridge.');
    const reviewUrl = page.url();
    await page.getByText('Reviewers', { exact: true }).click();
    await page.getByLabel('Reviewer email').fill(`${subject}@e2e.test`);
    await page.getByRole('button', { name: 'Add reviewer', exact: true }).click();
    await expect(page.getByText(`${subject}@e2e.test`, { exact: false }).last()).toBeVisible();
    const reviewPage = await reviewContext.newPage();
    await reviewPage.goto(reviewUrl);
    await expect(reviewPage.locator('article')).toContainText(
      'The river remembers the old bridge.',
    );
    await expect(reviewPage.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveCount(
      0,
    );
    await reviewPage
      .getByLabel('Review note', { exact: true })
      .fill('Could the bridge appear earlier?');
    await reviewPage.getByRole('button', { name: 'Save note', exact: true }).click();
    await expect(
      reviewPage.getByText('Could the bridge appear earlier?', { exact: true }).first(),
    ).toBeVisible();
    await reviewPage.getByRole('button', { name: 'Edit your note', exact: true }).click();
    await reviewPage
      .getByLabel('Review note', { exact: true })
      .fill('Could the bridge appear in Chapter one?');
    await reviewPage.getByRole('button', { name: 'Save note', exact: true }).click();
    await expect(
      reviewPage.getByText('Could the bridge appear in Chapter one?', { exact: true }).first(),
    ).toBeVisible();
    await reviewPage.screenshot({
      path: test.info().outputPath('review-desktop.png'),
      fullPage: true,
    });
    await reviewPage.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page: reviewPage }).analyze()).violations).toEqual([]);
    await reviewPage.screenshot({
      path: test.info().outputPath('review-phone.png'),
      fullPage: true,
    });
    await page.reload();
    await expect(
      page.getByText('Could the bridge appear in Chapter one?', { exact: true }),
    ).toBeVisible();
    await page.getByText('Reviewers', { exact: true }).click();
    await page.getByRole('button', { name: 'Revoke review access', exact: true }).click();
    // An already-open review is cleared by its next periodic authorization check.
    await expect(reviewPage.locator('article')).toHaveCount(0, { timeout: 40000 });
    await expect(reviewPage.getByRole('alert')).toBeVisible();
    await expect(reviewPage.getByLabel('Review note', { exact: true })).toHaveCount(0);
    await reviewPage.reload();
    await expect(reviewPage.getByRole('alert')).toBeVisible();
    await expect(reviewPage.locator('article')).toHaveCount(0);
  } finally {
    await reviewContext.close();
    await context.close();
  }
});

test('move a Chapter into another Chapter, promote it and recover an unassigned draft', async ({
  browser,
}) => {
  test.setTimeout(150000);
  const { page, context, tenant } = await world(browser);
  try {
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('Moving book');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Moving book', exact: true })).toBeVisible();
    const edition = new URL(page.url()).searchParams.get('entry');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    for (const title of ['Arrival', 'Departure']) {
      await page.getByLabel('New chapter title').fill(title);
      await page.getByRole('button', { name: 'Add chapter', exact: true }).click();
      await expect(page.getByRole('link', { name: title, exact: true })).toBeVisible();
    }
    await page.getByRole('link', { name: 'Arrival', exact: true }).click();
    const arrival = new URL(page.url()).searchParams.get('entry');
    await page
      .getByRole('textbox', { name: 'Manuscript', exact: true })
      .fill('The harbour is quiet.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=outline`);
    await page.getByLabel('Move: Arrival', { exact: true }).click();
    await page.getByLabel('Destination for Arrival').fill('Departure');
    await page.getByRole('button', { name: 'Find destination', exact: true }).click();
    await page.getByRole('button', { name: 'Departure', exact: true }).click();
    await page.getByRole('button', { name: 'Move here', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Arrival', exact: true })).toHaveCount(0);
    await page.getByRole('link', { name: 'Departure', exact: true }).click();
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByLabel('Move: Arrival', { exact: true }).click();
    await page.getByRole('button', { name: 'Promote one level', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Arrival', exact: true })).toHaveCount(0);
    await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=outline`);
    await page.getByLabel('Move: Arrival', { exact: true }).click();
    await page.getByRole('button', { name: 'Make unassigned', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Arrival', exact: true })).toHaveCount(0);
    await page.goto(`/?tenant=${tenant.id}&entry=${arrival}&view=outline`);
    await page.getByLabel('Move: Arrival', { exact: true }).click();
    await page.getByLabel('Destination for Arrival').fill('Moving book');
    await page.getByRole('button', { name: 'Find destination', exact: true }).click();
    await page.getByRole('button', { name: 'Moving book', exact: true }).click();
    await page.screenshot({ path: test.info().outputPath('move-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({ path: test.info().outputPath('move-phone.png'), fullPage: true });
    await page.getByRole('button', { name: 'Move here', exact: true }).click();
    await expect(page.getByLabel('Destination for Arrival')).toHaveCount(0);
    await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=read`);
    await expect(page.locator('article')).toContainText('The harbour is quiet.');
  } finally {
    await context.close();
  }
});

test('extract complete prose and a child into a Chapter without changing the reading', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context, tenant } = await world(browser);
  try {
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('Collected journeys');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    const prose = 'A **whole** passage[^a].\n\n[^a]: The local footnote stays.';
    await manuscript.fill(prose);
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const edition = new URL(page.url()).searchParams.get('entry');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByLabel('New chapter title').fill('The crossing');
    await page.getByRole('button', { name: 'Add chapter', exact: true }).click();
    await page.getByRole('link', { name: 'The crossing', exact: true }).click();
    await manuscript.fill('The boat reached the shore.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=outline`);
    await page.getByText('Extract a Chapter', { exact: true }).click();
    await page.getByLabel('First element', { exact: true }).selectOption('0');
    await page.getByLabel('Last element', { exact: true }).selectOption('1');
    await page.getByLabel('Extracted chapter title', { exact: true }).fill('At sea');
    await page.screenshot({
      path: test.info().outputPath('extraction-desktop.png'),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({ path: test.info().outputPath('extraction-phone.png'), fullPage: true });
    await page.getByRole('button', { name: 'Extract Chapter', exact: true }).click();
    await expect(page.getByRole('link', { name: 'At sea', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'The crossing', exact: true })).toHaveCount(0);
    await page.getByRole('link', { name: 'Read', exact: true }).click();
    await expect(page.locator('article')).toContainText('The local footnote stays.');
    await expect(page.locator('article')).toContainText('The boat reached the shore.');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByRole('link', { name: 'At sea', exact: true }).click();
    await expect(manuscript).toHaveValue(prose);
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await expect(page.getByRole('link', { name: 'The crossing', exact: true })).toBeVisible();
  } finally {
    await context.close();
  }
});

test('split saved prose safely and extract its second part into a Chapter', async ({ browser }) => {
  test.setTimeout(120000);
  const { page, context, tenant } = await world(browser);
  try {
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('A divided journey');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    const first =
      '# Dawn\n\nFirst 🐉[^a].\n\n- One\n\n  Still the same list.\n\n[^a]: A local note.\n\n';
    const second = '# Dusk';
    await manuscript.fill(first + second);
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByText('Split text', { exact: true }).click();
    const savedText = page.getByRole('textbox', { name: 'Text to split', exact: true });
    await expect(savedText).toHaveValue(first + second);
    await savedText.focus();
    await savedText.evaluate((element: HTMLTextAreaElement) => {
      element.setSelectionRange(element.value.indexOf('  Still'), element.value.indexOf('  Still'));
    });
    await page.getByRole('button', { name: 'Choose section', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Split here', exact: true })).toBeHidden();
    await expect(page.getByRole('status').filter({ hasText: 'Keep lists' })).toBeVisible();
    await savedText.focus();
    // Edge scrolls a readonly textarea on Ctrl+End without moving its selection.
    // Set the selected location explicitly, as for the rejected list boundary above.
    await savedText.evaluate((element: HTMLTextAreaElement) => {
      element.setSelectionRange(element.value.length, element.value.length);
    });
    await page.getByRole('button', { name: 'Choose section', exact: true }).click();
    await expect(
      page.getByRole('status').filter({ hasText: 'The second text block will begin:' }),
    ).toContainText(second);
    await page.screenshot({ path: test.info().outputPath('split-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({ path: test.info().outputPath('split-phone.png'), fullPage: true });
    await page.getByRole('button', { name: 'Split here', exact: true }).click();
    await expect(page.getByText('Split text', { exact: true })).toHaveCount(2);
    await page.getByText('Extract a Chapter', { exact: true }).click();
    await page.getByLabel('First element', { exact: true }).selectOption('1');
    await page.getByLabel('Last element', { exact: true }).selectOption('1');
    await page.getByLabel('Extracted chapter title', { exact: true }).fill('A new beginning');
    await page.getByRole('button', { name: 'Extract Chapter', exact: true }).click();
    await expect(page.getByRole('link', { name: 'A new beginning', exact: true })).toBeVisible();
    await page.getByRole('link', { name: 'Read', exact: true }).click();
    await expect(page.locator('article')).toContainText('A local note.');
    await expect(page.locator('article')).toContainText('Dusk');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByRole('link', { name: 'A new beginning', exact: true }).click();
    await expect(manuscript).toHaveValue(second);
  } finally {
    await context.close();
  }
});

test('join adjacent Chapters and follow the preserved source to its stable section', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context, tenant, api } = await world(browser);
  try {
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('Joined journeys');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    const text = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await expect(text).toBeVisible();
    const edition = new URL(page.url()).searchParams.get('entry');
    const ids: string[] = [];
    for (const [name, prose] of [
      ['Dawn', 'The first **account**.'],
      ['Dusk', 'The second account[^a].\n\n[^a]: A local note.'],
    ]) {
      await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=outline`);
      await page.getByLabel('New chapter title').fill(name);
      await page.getByRole('button', { name: 'Add chapter', exact: true }).click();
      await page.getByRole('link', { name, exact: true }).click();
      await expect(text).toBeVisible();
      const entryId = new URL(page.url()).searchParams.get('entry');
      if (!entryId) throw new Error('The Chapter address is missing.');
      ids.push(entryId);
      await text.fill(prose);
      await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    }
    await ok(
      api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { tenant_id: tenant.id, entity_id: ids[1] } },
        body: {
          type: 'note',
          title: 'Research',
          content: 'Keep this source note.',
          is_public: false,
          locale: 'en',
        },
      }),
    );
    await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=outline`);
    await page.getByText('Join with previous', { exact: true }).click();
    await expect(page.getByRole('button', { name: 'Join chapters', exact: true })).toBeVisible();
    await page.screenshot({ path: test.info().outputPath('join-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({ path: test.info().outputPath('join-phone.png'), fullPage: true });
    await page.getByRole('button', { name: 'Join chapters', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Dusk', exact: true })).toHaveCount(0);
    await page.goto(`/?tenant=${tenant.id}&entry=${ids[1]}`);
    await expect(text).toHaveCount(0);
    await expect(page.getByText('Keep this source note.', { exact: true })).toBeVisible();
    await page.getByRole('link', { name: 'Open joined section in Dawn', exact: true }).click();
    await expect(page.locator('article')).toContainText('The first account.');
    await expect(page.locator('article')).toContainText('The second account');
    await expect(page.locator('article')).toContainText('A local note.');
    const anchor = new URL(page.url()).hash;
    await expect(page.locator(anchor)).toContainText('The second account');
    await page.getByRole('link', { name: 'Write', exact: true }).click();
    await expect(text.first()).toHaveValue('The first **account**.');
    const secondText = page.getByRole('textbox', { name: 'Text 2', exact: true });
    await secondText.fill('A revised second account.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${ids[1]}`);
    await page.getByRole('link', { name: 'Open joined section in Dawn', exact: true }).click();
    await expect(page.locator('article')).toContainText('A revised second account.');
  } finally {
    await context.close();
  }
});
