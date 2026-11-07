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
    await page.getByText('Word count', { exact: true }).click();
    await page.getByText('Writing session', { exact: true }).click();
    await page.getByRole('button', { name: 'Start session', exact: true }).click();
    await text.focus();
    await text.press('Control+End');
    await text.press('a');
    const before = await text.evaluate((el) => (el as HTMLTextAreaElement).selectionStart);
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved', {
      timeout: 15000,
    });
    await expect(text).toBeFocused();
    expect(await text.evaluate((el) => (el as HTMLTextAreaElement).selectionStart)).toBe(before);
    await expect(page.getByText('Session progress · +1 word', { exact: true })).toBeVisible();
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
    await reviewPage.getByText('Word count', { exact: true }).click();
    await expect(
      reviewPage.getByText('Assembled manuscript · 6 words', { exact: true }),
    ).toBeVisible();
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
    await expect(reviewPage.getByText('Word count', { exact: true })).toHaveCount(0);
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
    await page.getByText('Word count', { exact: true }).click();
    await page.getByText('Writing session', { exact: true }).click();
    await page.getByRole('button', { name: 'Start session', exact: true }).click();
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
    await page.getByText('Word count', { exact: true }).click();
    await page.getByText('Writing session', { exact: true }).click();
    await expect(page.getByText('Session progress · 0 words', { exact: true })).toBeVisible();
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

test('join a Chapter into its parent without moving the surrounding prose', async ({ browser }) => {
  test.setTimeout(120000);
  const { page, context, tenant, api } = await world(browser);
  try {
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('One continuous account');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    const text = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await expect(text).toBeVisible();
    const parent = new URL(page.url()).searchParams.get('entry');
    if (!parent) throw new Error('The Edition address is missing.');
    await text.fill('Before the encounter.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${parent}&view=outline`);
    await page.getByLabel('New chapter title').fill('Encounter');
    await page.getByRole('button', { name: 'Add chapter', exact: true }).click();
    await page.getByRole('link', { name: 'Encounter', exact: true }).click();
    await expect(text).toBeVisible();
    const source = new URL(page.url()).searchParams.get('entry');
    await text.fill('Inside the encounter.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const readParent = () =>
      ok(
        api.GET('/tenants/{tenant_id}/writing/entries/{id}', {
          params: { path: { tenant_id: tenant.id, id: parent } },
        }),
      );
    const original = await readParent();
    const entity = await ok(
      api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenant.id, entity_id: parent } },
      }),
    );
    const manuscript = entity.information.find((info) => info.type === 'manuscript');
    if (!manuscript) throw new Error('The parent manuscript is missing.');
    const infoResponse = await api.GET('/tenants/{tenant_id}/information/{information_id}', {
      params: { path: { tenant_id: tenant.id, information_id: manuscript.id } },
    });
    await ok(Promise.resolve(infoResponse));
    const after = await ok(
      api.POST('/tenants/{tenant_id}/information/{information_id}/texts', {
        params: {
          path: { tenant_id: tenant.id, information_id: manuscript.id },
          header: { 'if-match': infoResponse.response.headers.get('etag') ?? '' },
        },
        body: { content: 'After the encounter.', locale: 'en-US' },
      }),
    );
    const current = await readParent();
    await ok(
      api.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
        params: {
          path: { tenant_id: tenant.id, id: parent },
          header: { 'if-match': current.version },
        },
        body: { elements: [...original.elements.map((e) => e.id), after.id] },
      }),
    );
    await page.goto(`/?tenant=${tenant.id}&entry=${parent}&view=outline`);
    await page.getByText('Join into parent', { exact: true }).click();
    await expect(page.getByRole('button', { name: 'Join chapters', exact: true })).toBeVisible();
    await page.screenshot({
      path: test.info().outputPath('parent-join-desktop.png'),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({
      path: test.info().outputPath('parent-join-phone.png'),
      fullPage: true,
    });
    await page.getByRole('button', { name: 'Join chapters', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Encounter', exact: true })).toHaveCount(0);
    await page.goto(`/?tenant=${tenant.id}&entry=${source}`);
    await expect(text).toHaveCount(0);
    await page
      .getByRole('link', { name: 'Open joined section in One continuous account', exact: true })
      .click();
    await expect(page.locator('article')).toContainText(
      /Before the encounter\.[\s\S]*Inside the encounter\.[\s\S]*After the encounter\./,
    );
    await expect(page.locator(new URL(page.url()).hash)).toContainText('Inside the encounter.');
    await page.getByRole('link', { name: 'Write', exact: true }).click();
    await page.getByRole('textbox', { name: 'Text 2', exact: true }).fill('Revised encounter.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
  } finally {
    await context.close();
  }
});

test('extract a reusable Scene and make its second telling independent', async ({ browser }) => {
  test.setTimeout(120000);
  const { page, context, tenant } = await world(browser);
  try {
    await page.goto(`/?tenant=${tenant.id}`);
    await page.getByLabel('Start with').selectOption('book');
    await page.getByLabel('New draft title').fill('Shared crossings');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    const prose = 'The river **remembers**.';
    await manuscript.fill(prose);
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.locator('input[type=file]').setInputFiles({
      name: 'idea.png',
      mimeType: 'image/png',
      buffer: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
        'base64',
      ),
    });
    await expect(page.getByRole('button', { name: 'Remove picture' })).toBeVisible();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const edition = new URL(page.url()).searchParams.get('entry');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByText('Extract a Scene', { exact: true }).click();
    await page.getByLabel('Extracted scene title', { exact: true }).fill('At the crossing');
    await page.screenshot({
      path: test.info().outputPath('scene-extraction-desktop.png'),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({
      path: test.info().outputPath('scene-extraction-phone.png'),
      fullPage: true,
    });
    await page.getByRole('button', { name: 'Extract Scene', exact: true }).click();
    await expect(page.getByRole('link', { name: 'At the crossing', exact: true })).toHaveCount(1);
    await page.getByText('Use a Scene', { exact: true }).click();
    await page.getByLabel('Find a Scene', { exact: true }).fill('At the crossing');
    await page.getByRole('button', { name: 'Find Scenes', exact: true }).click();
    await page.getByRole('button', { name: 'At the crossing', exact: true }).click();
    await expect(page.getByRole('link', { name: 'At the crossing', exact: true })).toHaveCount(2);
    await page.getByRole('link', { name: 'At the crossing', exact: true }).last().click();
    await expect(page.locator('article')).toContainText('The river remembers.');
    await page.getByRole('button', { name: 'Make independent', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Remove picture' })).toBeVisible();
    await expect(manuscript).toHaveValue(prose);
    await manuscript.fill('The ferryman remembers.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=read`);
    await expect(page.locator('article')).toHaveText(
      /The river remembers.*The ferryman remembers/s,
    );
  } finally {
    await context.close();
  }
});

test('a Carrier inherits several forms and reads selected writing alongside its own prose', async ({
  browser,
}) => {
  test.setTimeout(150000);
  const { page, context, tenant } = await world(browser);
  try {
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await manuscript.fill('The river remembers.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const scene = new URL(page.url()).searchParams.get('entry');
    for (const name of ['Vellum', 'Coptic', 'Collected codex']) {
      await page.goto(`/?tenant=${tenant.id}`);
      await page.getByLabel('Start with').selectOption('carrier');
      await page.getByLabel('New draft title').fill(name);
      await page.getByRole('button', { name: 'Start writing', exact: true }).click();
      await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    }
    await manuscript.fill('A note on this binding.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const carrier = new URL(page.url()).searchParams.get('entry');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    for (const name of ['Vellum', 'Coptic']) {
      await page.getByText('Carrier form', { exact: true }).click();
      await page.getByText('Carrier prototypes', { exact: true }).click();
      await page.getByLabel('Carrier prototypes', { exact: true }).fill(name);
      await page.getByRole('button', { name: 'Find carrier prototypes', exact: true }).click();
      await page.getByRole('button', { name, exact: true }).click();
      await expect(
        page.getByRole('button', { name: `Remove ${name}`, exact: true, includeHidden: true }),
      ).toHaveCount(1);
    }
    await page.getByText('Covered writing', { exact: true }).click();
    await page.getByLabel('Covered writing', { exact: true }).fill('Across the water');
    await page.getByRole('button', { name: 'Find covered writing', exact: true }).click();
    await page.getByRole('button', { name: 'Across the water', exact: true }).click();
    await page
      .getByRole('button', { name: 'Include block: The river remembers.', exact: true })
      .click();
    await expect(
      page.getByRole('link', { name: 'Across the water · selected block', exact: true }),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Up', exact: true }).last().click();
    await expect(page.locator('main')).toHaveText(
      /Across the water · selected block[\s\S]*A note on this binding/,
    );
    await page.getByText('Carrier form', { exact: true }).click();
    await page.screenshot({ path: test.info().outputPath('carrier-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: test.info().outputPath('carrier-phone.png'), fullPage: true });
    await page.getByRole('link', { name: 'Read', exact: true }).click();
    await expect(page.locator('article')).toHaveText(
      /The river remembers.*A note on this binding/s,
    );
    await page.goto(`/?tenant=${tenant.id}&entry=${scene}`);
    await manuscript.fill('The river changed.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.goto(`/?tenant=${tenant.id}&entry=${carrier}&view=read`);
    await expect(page.locator('article')).toContainText('The river changed.');
    await page.getByRole('link', { name: 'Outline', exact: true }).click();
    await page.getByRole('button', { name: 'Remove coverage', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Remove coverage', exact: true })).toHaveCount(0);
    await page.goto(`/?tenant=${tenant.id}&entry=${scene}`);
    await expect(manuscript).toHaveValue('The river changed.');
  } finally {
    await context.close();
  }
});

test('Chapter numbering follows the outline without changing titles', async ({ browser }) => {
  test.setTimeout(150000);
  const { page, context, tenant, api } = await world(browser);
  try {
    const book = await ok(
      api.POST('/tenants/{tenant_id}/writing/books', {
        params: { path: { tenant_id: tenant.id } },
        body: { name: 'Numbered journeys' },
      }),
    );
    const edition = book.editions[0].id;
    const chapters = [];
    for (const name of ['Departure', 'Arrival', 'The ferry'])
      chapters.push(
        await ok(
          api.POST('/tenants/{tenant_id}/writing/chapters', {
            params: { path: { tenant_id: tenant.id } },
            body: { name },
          }),
        ),
      );
    const [first, second, nested] = chapters;
    const arrange = async (id: string, elements: string[]) => {
      const current = await ok(
        api.GET('/tenants/{tenant_id}/writing/entries/{id}', {
          params: { path: { tenant_id: tenant.id, id } },
        }),
      );
      await ok(
        api.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
          params: { path: { tenant_id: tenant.id, id }, header: { 'if-match': current.version } },
          body: { elements },
        }),
      );
    };
    await arrange(edition, [first.id, second.id]);
    await arrange(first.id, [nested.id]);
    await page.goto(`/?tenant=${tenant.id}&entry=${edition}&view=outline`);
    await page.getByText('Numbering', { exact: true }).click();
    await page.getByLabel('Number Chapters', { exact: true }).check();
    await page.getByRole('combobox', { name: 'Number style', exact: true }).selectOption('roman');
    await page.getByRole('button', { name: 'Add level', exact: true }).click();
    const levelTwo = page.getByRole('group', { name: 'Level 2', exact: true });
    await levelTwo.getByLabel('Number style').selectOption('alphabetic_lower');
    await page.getByRole('button', { name: 'Save numbering', exact: true }).click();
    await expect(page.getByRole('link', { name: 'I Departure', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'II Arrival', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Up: Arrival', exact: true }).click();
    await expect(page.getByRole('link', { name: 'I Arrival', exact: true })).toBeVisible();
    await page.getByRole('link', { name: 'Read', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'II.a The ferry', exact: true })).toBeVisible();
    await page.goto(`/?tenant=${tenant.id}&entry=${first.id}&view=outline`);
    await page.getByText('Numbering', { exact: true }).click();
    await page.getByLabel('Use this number (optional)', { exact: true }).fill('5');
    await page.getByRole('button', { name: 'Save numbering', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'V Departure', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'V.a The ferry', exact: true })).toBeVisible();
    await page.getByText('Numbering', { exact: true }).click();
    await page.screenshot({
      path: test.info().outputPath('numbering-desktop.png'),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole('button', { name: 'Save numbering', exact: true })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: test.info().outputPath('numbering-phone.png'), fullPage: true });
    await page.reload();
    await expect(page.getByRole('heading', { name: 'V Departure', exact: true })).toBeVisible();
    const unchanged = await ok(
      api.GET('/tenants/{tenant_id}/writing/entries/{id}', {
        params: { path: { tenant_id: tenant.id, id: first.id } },
      }),
    );
    expect(unchanged.name).toBe('Departure');
  } finally {
    await context.close();
  }
});

test('structural contents link Chapters while special Chapters keep authored text', async ({
  browser,
}) => {
  test.setTimeout(150000);
  const { page, context, tenant, api } = await world(browser);
  try {
    const book = await ok(
      api.POST('/tenants/{tenant_id}/writing/books', {
        params: { path: { tenant_id: tenant.id } },
        body: { name: 'River manuscript' },
      }),
    );
    const edition = book.editions[0].id;
    const chapters = [];
    for (const name of ['Guide', 'Crossing', 'Ferry', 'Glossary'])
      chapters.push(
        await ok(
          api.POST('/tenants/{tenant_id}/writing/chapters', {
            params: { path: { tenant_id: tenant.id } },
            body: { name },
          }),
        ),
      );
    const [guide, chapter, nested, glossary] = chapters;
    const arrange = async (id: string, elements: string[]) => {
      const current = await ok(
        api.GET('/tenants/{tenant_id}/writing/entries/{id}', {
          params: { path: { tenant_id: tenant.id, id } },
        }),
      );
      await ok(
        api.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
          params: { path: { tenant_id: tenant.id, id }, header: { 'if-match': current.version } },
          body: { elements },
        }),
      );
    };
    await arrange(edition, [guide.id, chapter.id, glossary.id]);
    await arrange(chapter.id, [nested.id]);
    await ok(
      api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { tenant_id: tenant.id, entity_id: glossary.id } },
        body: {
          title: 'Manuscript',
          type: 'manuscript',
          content: '**Ferry**: a boat crossing the river.',
          is_public: false,
          locale: 'en',
        },
      }),
    );
    const outline = async (id: string) => {
      await page.goto(`/?tenant=${tenant.id}&entry=${id}&view=outline`);
      await page
        .locator('summary')
        .filter({ hasText: /^Contents$/ })
        .click();
    };
    await outline(edition);
    await page.getByLabel('Show contents before the manuscript').check();
    await page.getByLabel('Contents label template').fill('{title}');
    await page.getByRole('button', { name: 'Save contents settings', exact: true }).click();
    await page.getByRole('link', { name: 'Read', exact: true }).click();
    let navigation = page.getByRole('navigation', { name: 'Contents', exact: true });
    await expect(navigation.getByRole('link')).toHaveText([
      'Guide',
      'Crossing',
      'Ferry',
      'Glossary',
    ]);
    await navigation.getByRole('link', { name: 'Ferry', exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`#element-${nested.id}$`));
    await expect(page.locator(`#element-${nested.id}`)).toBeInViewport();
    await outline(chapter.id);
    await page.getByLabel('Include in contents', { exact: true }).uncheck();
    await page.getByRole('button', { name: 'Save contents settings', exact: true }).click();
    await outline(guide.id);
    await page
      .getByRole('combobox', { name: 'Chapter type', exact: true })
      .selectOption('contents');
    await page.getByLabel('Include in contents', { exact: true }).uncheck();
    await page.getByRole('button', { name: 'Save contents settings', exact: true }).click();
    await outline(glossary.id);
    await page
      .getByRole('combobox', { name: 'Chapter type', exact: true })
      .selectOption('glossary');
    await page.getByRole('button', { name: 'Save contents settings', exact: true }).click();
    await outline(edition);
    await page.getByLabel('Show contents before the manuscript').uncheck();
    await page.getByLabel('Chapter levels to include').fill('1');
    await page.getByRole('button', { name: 'Save contents settings', exact: true }).click();
    await page.getByRole('link', { name: 'Read', exact: true }).click();
    navigation = page.getByRole('navigation', { name: 'Contents', exact: true });
    await expect(navigation.getByRole('link')).toHaveText(['Glossary']);
    await expect(page.locator('article')).toContainText('Ferry: a boat crossing the river.');
    await outline(edition);
    await page.getByLabel('Chapter levels to include').fill('3');
    await page.getByLabel('Contents label template').fill('<b>{title}</b>');
    await page.getByRole('button', { name: 'Save contents settings', exact: true }).click();
    await page.getByRole('link', { name: 'Read', exact: true }).click();
    await expect(navigation.getByRole('link')).toHaveText(['<b>Ferry</b>', '<b>Glossary</b>']);
    await expect(navigation.locator('b')).toHaveCount(0);
    await expect(page.locator('article')).toContainText('Ferry: a boat crossing the river.');
    await page.screenshot({ path: test.info().outputPath('contents-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: test.info().outputPath('contents-phone.png'), fullPage: true });
    await page.goto(`/?tenant=${tenant.id}&review=${edition}`);
    const reviewContents = page.getByRole('navigation', { name: 'Contents', exact: true });
    await expect(reviewContents.getByRole('link')).toHaveText(['<b>Ferry</b>', '<b>Glossary</b>']);
    await reviewContents.getByRole('link', { name: '<b>Glossary</b>', exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`#review-entry-${glossary.id}$`));
    await expect(page.locator(`#review-entry-${glossary.id}`)).toBeInViewport();
  } finally {
    await context.close();
  }
});

test('word counts measure direct prose, repeated Carrier passages and highlighted text', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context, tenant, api } = await world(browser);
  try {
    const scene = new URL(page.url()).searchParams.get('entry');
    if (!scene) throw new Error('Scene did not open');
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await page.getByText('Word count', { exact: true }).click();
    await expect(page.getByText('Current draft · 0 words', { exact: true })).toBeVisible();
    const source =
      '# Étoile\n\nThe [water**fall**](https://example.test/extra/words) sings.[^n] 猫[^n]\n\n{{TOC}}\n\n`omit these words` $x$\n\n[^n]: One small note.';
    await manuscript.fill(source);
    await expect(page.getByText('Current draft · 8 words', { exact: true })).toBeVisible();
    await expect(manuscript).toBeFocused();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const entry = await ok(
      api.GET('/tenants/{tenant_id}/writing/entries/{id}', {
        params: { path: { tenant_id: tenant.id, id: scene } },
      }),
    );
    const payload = entry.elements.find((item) => item.kind === 'payload');
    if (!payload) throw new Error('Scene prose was not saved');
    const carrier = await ok(
      api.POST('/tenants/{tenant_id}/writing/carriers', {
        params: { path: { tenant_id: tenant.id } },
        body: { name: 'Long title outside the word count' },
      }),
    );
    await ok(
      api.PUT('/tenants/{tenant_id}/writing/carriers/{id}/coverage', {
        params: {
          path: { tenant_id: tenant.id, id: carrier.id },
          header: { 'if-match': carrier.version },
        },
        body: {
          elements: [
            { id: randomUUID(), target_entity_id: scene },
            { id: randomUUID(), target_payload_id: payload.id },
          ],
        },
      }),
    );
    await page.goto(`/?tenant=${tenant.id}&entry=${carrier.id}&view=read`);
    await page.getByText('Word count', { exact: true }).click();
    await expect(page.getByText('Assembled manuscript · 16 words', { exact: true })).toBeVisible();
    await page.getByText('Choose passages', { exact: true }).click();
    const choices = page.getByRole('checkbox', { name: /^Passage / });
    await expect(choices).toHaveCount(2);
    await choices.first().check();
    await expect(page.getByText('Chosen passages · 8 words', { exact: true })).toBeVisible();
    await choices.last().check();
    await expect(page.getByText('Chosen passages · 16 words', { exact: true })).toBeVisible();
    await page
      .getByRole('link', { name: 'waterfall', exact: true })
      .first()
      .evaluate((link) => {
        const range = document.createRange();
        range.selectNodeContents(link);
        const selection = document.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      });
    await expect(page.getByText('Highlighted passage · 1 word', { exact: true })).toBeVisible();
    await page.locator('article').evaluate((article) => {
      const blocks = article.querySelectorAll(':scope > section');
      const start = blocks[0].querySelector('.ls-footnotes p')?.firstChild;
      const end = blocks[1].querySelector('h1')?.firstChild;
      if (!start || !end) throw new Error('Missing rendered footnote or heading');
      const range = document.createRange();
      range.setStart(start, (start.textContent ?? '').indexOf('note') + 1);
      range.setEnd(end, 3);
      const selection = document.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
    });
    await expect(page.getByText('Highlighted passage · 2 words', { exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    // The count UI introduces no new accessibility violations.
    expect((await new AxeBuilder({ page }).include('details').analyze()).violations).toEqual([]);
  } finally {
    await context.close();
  }
});

test('personal targets persist independently for the draft and assembled reading', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context } = await world(browser);
  try {
    const writeUrl = page.url();
    await page.getByText('Word count', { exact: true }).click();
    await page.getByLabel('Personal word target').fill('5');
    await page.getByRole('button', { name: 'Save target', exact: true }).click();
    await expect(page.getByText('Target saved.', { exact: true })).toBeVisible();
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await manuscript.fill('The river remembers.');
    await expect(page.getByText('2 words remaining · target 5', { exact: true })).toBeVisible();
    await manuscript.fill('The river remembers every crossing.');
    await expect(page.getByText('Target reached · 5 words', { exact: true })).toBeVisible();
    await expect(manuscript).toBeFocused();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.reload();
    await page.getByText('Word count', { exact: true }).click();
    await expect(page.getByLabel('Personal word target')).toHaveValue('5');
    const readUrl = new URL(writeUrl);
    readUrl.searchParams.set('view', 'read');
    await page.goto(readUrl.toString());
    await page.getByText('Word count', { exact: true }).click();
    await expect(page.getByLabel('Personal word target')).toHaveValue('');
    await page.getByLabel('Personal word target').fill('10');
    await page.getByRole('button', { name: 'Save target', exact: true }).click();
    await expect(page.getByText('5 words remaining · target 10', { exact: true })).toBeVisible();
    await page.reload();
    await page.getByText('Word count', { exact: true }).click();
    await expect(page.getByLabel('Personal word target')).toHaveValue('10');
    await page.getByRole('button', { name: 'Clear target', exact: true }).click();
    await expect(page.getByText('Target cleared.', { exact: true })).toBeVisible();
    await page.goto(writeUrl);
    await page.getByText('Word count', { exact: true }).click();
    await expect(page.getByLabel('Personal word target')).toHaveValue('5');
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  } finally {
    await context.close();
  }
});

test('personal timer pauses, resumes, survives reload and stays separate from another account', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context, tenant, owner } = await world(browser);
  try {
    const now = new Date();
    await page.clock.install({ time: now });
    await page.clock.pauseAt(now);
    const openTimer = async () => {
      await page.getByText('Word count', { exact: true }).click();
      await page.getByText('Writing timer', { exact: true }).click();
    };
    await openTimer();
    await page.getByLabel('Minutes', { exact: true }).fill('1');
    await page.getByRole('button', { name: 'Start timer', exact: true }).click();
    await page.clock.runFor(10_000);
    await expect(page.getByRole('timer')).toHaveText('0:50');
    await page.getByRole('button', { name: 'Pause timer', exact: true }).click();
    await page.clock.runFor(15_000);
    await expect(page.getByRole('timer')).toHaveText('0:50');
    await page.reload();
    await openTimer();
    await expect(page.getByRole('timer')).toHaveText('0:50');
    await page.getByRole('link', { name: 'Your writing', exact: true }).click();
    await page.getByLabel('New draft title').fill('Another passage');
    await page.getByRole('button', { name: 'Start writing', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toBeVisible();
    await openTimer();
    await expect(page.getByRole('timer')).toHaveText('0:50');
    await page.getByRole('button', { name: 'Resume timer', exact: true }).click();
    await page.clock.runFor(10_000);
    await page.reload();
    await openTimer();
    await expect(page.getByRole('timer')).toHaveText('0:40');
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await manuscript.focus();
    await page.clock.runFor(40_000);
    await expect(page.getByText('Time elapsed.', { exact: true })).toBeVisible();
    await expect(manuscript).toBeFocused();
    await page.getByRole('button', { name: 'Reset timer', exact: true }).click();
    await expect(page.getByRole('timer')).toHaveText('1:00');
    await page.clock.resume();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    // A second Author in the same tab must get their own default timer.
    const subject = `timer-other-${randomUUID()}`;
    const api = await apiAs(subject);
    const user = await ok(api.GET('/me'));
    await ok(
      owner.POST('/tenants/{tenant_id}/memberships', {
        params: { path: { tenant_id: tenant.id } },
        body: { user_id: user.id, role: 'author' },
      }),
    );
    const token = await refreshTokenFor(subject);
    await page.evaluate(({ key, token }) => localStorage.setItem(key, token), {
      key: REFRESH_TOKEN_KEY,
      token,
    });
    await page.reload();
    await openTimer();
    await expect(page.getByRole('timer')).toHaveText('25:00');
  } finally {
    await context.close();
  }
});

test('a timer remains usable when tab storage is unavailable', async ({ browser }) => {
  const { page, context } = await world(browser);
  try {
    await page.addInitScript(() => {
      const get = Storage.prototype.getItem;
      const set = Storage.prototype.setItem;
      Storage.prototype.getItem = function (key) {
        if (key.startsWith('lorenzo:writing-timer:')) throw new Error('Storage blocked');
        return get.call(this, key);
      };
      Storage.prototype.setItem = function (key, value) {
        if (key.startsWith('lorenzo:writing-timer:')) throw new Error('Storage blocked');
        return set.call(this, key, value);
      };
    });
    await page.reload();
    await page.getByText('Word count', { exact: true }).click();
    await page.getByText('Writing timer', { exact: true }).click();
    await expect(
      page.getByText('This timer works here, but cannot be restored after reloading this tab.'),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Start timer', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Pause timer', exact: true })).toBeVisible();
  } finally {
    await context.close();
  }
});

test('session goals count signed editing changes and rebase loaded revisions', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context } = await world(browser);
  try {
    const manuscript = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    await manuscript.fill('The river remembers.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const open = async () => {
      await page.getByText('Word count', { exact: true }).click();
      await page.getByText('Writing session', { exact: true }).click();
    };
    await open();
    await page.getByLabel('Session word target').fill('2');
    await page.getByRole('button', { name: 'Start session', exact: true }).click();
    await page.route(`${API_URL}/tenants/**/payloads/*`, (route) =>
      route.request().method() === 'PATCH' ? route.abort() : route.continue(),
    );
    await manuscript.fill('The river remembers every crossing.');
    await expect(page.getByText('Session progress · +2 words', { exact: true })).toBeVisible();
    await expect(page.getByText('Session target reached.', { exact: true })).toBeVisible();
    await expect(manuscript).toBeFocused();
    await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
      'Use Save now to retry',
    );
    await page.unroute(`${API_URL}/tenants/**/payloads/*`);
    await page.getByRole('button', { name: 'Save now', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await expect(page.getByText('Session progress · +2 words', { exact: true })).toBeVisible();
    await manuscript.fill('The river.');
    await expect(page.getByText('Session progress · -1 word', { exact: true })).toBeVisible();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.reload();
    await open();
    await expect(page.getByText('Session progress · -1 word', { exact: true })).toBeVisible();
    await page.getByText('Saved revisions', { exact: true }).click();
    await page
      .locator('details')
      .filter({ has: page.getByText('Saved revisions', { exact: true }) })
      .getByRole('button')
      .first()
      .click();
    await page.getByRole('button', { name: 'Load this revision as a draft' }).click();
    await expect(manuscript).toHaveValue('The river remembers every crossing.');
    await expect(page.getByText('Session progress · -1 word', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Save now', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await expect(page.getByText('Session progress · -1 word', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Finish session', exact: true }).click();
    await manuscript.fill('An ending.');
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await expect(page.getByText('Session progress · -1 word', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Start new session', exact: true }).click();
    await manuscript.fill('An ending follows here.');
    await expect(page.getByText('Session progress · +2 words', { exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  } finally {
    await context.close();
  }
});

test('session progress does not credit another version or leak to another account', async ({
  browser,
}) => {
  const { page, context, api, owner, tenant } = await world(browser);
  try {
    const open = async () => {
      await page.getByText('Word count', { exact: true }).click();
      await page.getByText('Writing session', { exact: true }).click();
    };
    await open();
    await page.getByRole('button', { name: 'Start session', exact: true }).click();
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
        body: { content: 'Written elsewhere with many more words.' },
      }),
    );
    await page.getByRole('textbox', { name: 'Manuscript', exact: true }).fill('My words.');
    await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
      'changed elsewhere',
    );
    await page.getByRole('button', { name: 'Use saved manuscript', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Manuscript', exact: true })).toHaveValue(
      'Written elsewhere with many more words.',
    );
    await expect(page.getByText('Session progress · +2 words', { exact: true })).toBeVisible();
    const subject = `session-other-${randomUUID()}`;
    const other = await apiAs(subject);
    const user = await ok(other.GET('/me'));
    await ok(
      owner.POST('/tenants/{tenant_id}/memberships', {
        params: { path: { tenant_id: tenant.id } },
        body: { user_id: user.id, role: 'author' },
      }),
    );
    await page.evaluate(({ key, token }) => localStorage.setItem(key, token), {
      key: REFRESH_TOKEN_KEY,
      token: await refreshTokenFor(subject),
    });
    await page.reload();
    await open();
    await expect(page.getByRole('button', { name: 'Start session', exact: true })).toBeVisible();
    await expect(page.getByText('Session progress · +2 words', { exact: true })).toHaveCount(0);
  } finally {
    await context.close();
  }
});

test('session progress stays usable when local recovery is blocked', async ({ browser }) => {
  const { page, context } = await world(browser);
  try {
    await page.addInitScript(() => {
      const get = Storage.prototype.getItem;
      const set = Storage.prototype.setItem;
      Storage.prototype.getItem = function (key) {
        if (key.startsWith('lorenzo:writing-session:')) throw new Error('Storage blocked');
        return get.call(this, key);
      };
      Storage.prototype.setItem = function (key, value) {
        if (key.startsWith('lorenzo:writing-session:')) throw new Error('Storage blocked');
        return set.call(this, key, value);
      };
    });
    await page.reload();
    await page.getByText('Word count', { exact: true }).click();
    await page.getByText('Writing session', { exact: true }).click();
    await expect(
      page.getByText(
        'Session progress works here, but cannot be restored after reloading this tab.',
      ),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Start session', exact: true }).click();
    await page.getByRole('textbox', { name: 'Manuscript', exact: true }).fill('One');
    await expect(page.getByText('Session progress · +1 word', { exact: true })).toBeVisible();
  } finally {
    await context.close();
  }
});

test('an author reviews Being names before adding a private Scene reference', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context, api, owner, tenant } = await world(browser);
  try {
    const scene = new URL(page.url()).searchParams.get('entry') as string;
    const biography = (name: string) =>
      ok(
        api.POST('/tenants/{tenant_id}/writing/biographies', {
          params: { path: { tenant_id: tenant.id } },
          body: { name },
        }),
      );
    const eira = await biography('Eira Vale');
    const other = await biography('Rowan');
    for (const name of ['Ash', 'Ash', 'Codebird', 'North Bank']) await biography(name);
    const elsewhere = await ok(owner.POST('/tenants', { body: { name: 'Other shelves' } }));
    await ok(
      owner.POST('/tenants/{tenant_id}/writing/biographies', {
        params: { path: { tenant_id: elsewhere.id } },
        body: { name: 'Eira Vale' },
      }),
    );
    const path = { tenant_id: tenant.id, source_kind: 'scenes' as const, source_id: scene };
    const refs = () =>
      api.GET('/tenants/{tenant_id}/{source_kind}/{source_id}/references', { params: { path } });
    const draft = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    const source = 'Ei**ra** Vale meets Ash. `Codebird` rests.\n\nNorth\n\nBank';
    await draft.fill(source);
    await page.getByText('Details', { exact: true }).click();
    await page.getByText('Suggested Being references', { exact: true }).click();
    const check = page.getByRole('button', { name: 'Check names', exact: true });
    const add = page.getByRole('button', { name: 'Add reference to Eira Vale', exact: true });
    await check.click();
    await expect(add).toBeVisible();
    await expect(page.getByText(/Several Beings share the name Ash/)).toBeVisible();
    for (const name of ['Codebird', 'North Bank', 'Ash'])
      await expect(
        page.getByRole('button', { name: `Add reference to ${name}`, exact: true }),
      ).toHaveCount(0);
    expect(await ok(refs())).toEqual([]);
    const edited = `${source} The bell rings.`;
    await draft.fill(edited);
    await add.click();
    await expect(page.getByText('The draft changed. Check names again.')).toBeVisible();
    expect(await ok(refs())).toEqual([]);
    await check.click();
    const before = await refs();
    await ok(
      api.PUT('/tenants/{tenant_id}/{source_kind}/{source_id}/references/{kind}/{target_id}', {
        params: {
          path: { ...path, kind: 'beings', target_id: other.id },
          header: { 'if-match': before.response.headers.get('etag') as string },
        },
        body: { is_shared: false },
      }),
    );
    await add.click();
    await expect(page.getByText('The references changed. Check names again.')).toBeVisible();
    expect((await ok(refs())).map((ref) => ref.id)).toEqual([other.id]);
    await check.click();
    await add.click();
    await expect(page.getByText('Eira Vale (beings)', { exact: false })).toBeVisible();
    const saved = await ok(refs());
    expect(saved.find((ref) => ref.id === eira.id)?.is_shared).toBe(false);
    await expect(draft).toHaveValue(edited);
    await page.getByText('Suggested Being references', { exact: true }).click();
    await check.click();
    await expect(page.getByText(/Several Beings share the name Ash/)).toBeVisible();
    await expect(add).toHaveCount(0);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  } finally {
    await context.close();
  }
});

test('reviewed manuscript links preserve the selected wording, undo and saved backlink', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context, api, owner, tenant } = await world(browser);
  try {
    const scene = new URL(page.url()).searchParams.get('entry') as string;
    const create = async (slug: string) => {
      const entry = await ok(
        api.POST('/tenants/{tenant_id}/writing/biographies', {
          params: { path: { tenant_id: tenant.id } },
          body: { name: 'Eira Vale' },
        }),
      );
      await ok(
        owner.PUT('/tenants/{tenant_id}/entities/{entity_id}/slug', {
          params: { path: { tenant_id: tenant.id, entity_id: entry.id } },
          body: { slug },
        }),
      );
      return entry.id;
    };
    const writer = await create('harbour-scribe');
    const guide = await create('north-guide');
    const other = await ok(owner.POST('/tenants', { body: { name: 'Other library' } }));
    await ok(
      owner.POST('/tenants/{tenant_id}/entities', {
        params: { path: { tenant_id: other.id } },
        body: { name: 'Eira Vale', slug: 'other-eira', kinds: ['being'], parents: [] },
      }),
    );
    const draft = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    const source = 'eIRA Vale met Eira Vale.';
    await draft.fill(source);
    const select = async (start: number) =>
      draft.evaluate((el, from) => {
        const area = el as HTMLTextAreaElement;
        area.focus();
        area.setSelectionRange(from, from + 9);
      }, start);
    await select(0);
    await page.getByRole('button', { name: 'Link to an entity', exact: true }).click();
    const find = page.getByRole('button', { name: 'Find matching entries', exact: true });
    const choice = page.getByRole('button', { name: 'Eira Vale (harbour-scribe)', exact: true });
    await expect(choice).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Eira Vale (north-guide)', exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/other-eira/)).toHaveCount(0);
    await expect(draft).toHaveValue(source);
    await select(14);
    await choice.click();
    await expect(
      page.getByText('The selection changed. Select the name and search again.'),
    ).toBeVisible();
    await select(0);
    await find.click();
    const guideChoice = page.getByRole('button', { name: 'Eira Vale (north-guide)', exact: true });
    await expect(guideChoice).toBeVisible();
    await ok(
      owner.PUT('/tenants/{tenant_id}/entities/{entity_id}/slug', {
        params: { path: { tenant_id: tenant.id, entity_id: guide } },
        body: { slug: 'hill-guide' },
      }),
    );
    await guideChoice.click();
    await expect(page.getByText('The entry changed. Find matching entries again.')).toBeVisible();
    await find.click();
    await choice.click();
    const linked = '[[harbour-scribe|eIRA Vale]] met Eira Vale.';
    await expect(draft).toHaveValue(linked);
    await expect(draft).toBeFocused();
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    const backlinks = () =>
      ok(
        api.GET('/tenants/{tenant_id}/entities/{entity_id}/backlinks', {
          params: { path: { tenant_id: tenant.id, entity_id: writer } },
        }),
      );
    expect((await backlinks()).items.map((item) => item.entity_id)).toContain(scene);
    await page.getByRole('button', { name: 'Undo', exact: true }).click();
    await expect(draft).toHaveValue(source);
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    expect((await backlinks()).items).toHaveLength(0);
    await select(0);
    await page.getByRole('button', { name: 'Link to an entity', exact: true }).click();
    await expect(choice).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await choice.click();
    await expect(draft).toHaveValue(linked);
    await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
    await page.reload();
    await expect(draft).toHaveValue(linked);
  } finally {
    await context.close();
  }
});
test('an author reviews existing calendar dates before setting a Scene period', async ({
  browser,
}) => {
  test.setTimeout(120000);
  const { page, context, api, owner, tenant } = await world(browser);
  try {
    const scene = new URL(page.url()).searchParams.get('entry') as string;
    const path = { tenant_id: tenant.id, scene_id: scene };
    const calendar = async (name: string, tenantId = tenant.id) =>
      ok(
        owner.POST('/tenants/{tenant_id}/calendars', {
          params: { path: { tenant_id: tenantId } },
          body: {
            name,
            is_public: true,
            definition: {
              format: 'lorenzo.calendar/1',
              moons: [],
              segments: [{ key: 'frost', name: 'Frost', days: 30, kind: 'month', in_week: true }],
            },
          },
        }),
      );
    const first = await calendar('Coast reckoning');
    const second = await calendar('Mountain reckoning');
    const period = (calendarId: string, day: number, tenantId = tenant.id) =>
      ok(
        owner.POST('/tenants/{tenant_id}/calendars/{calendar_id}/periods', {
          params: { path: { tenant_id: tenantId, calendar_id: calendarId } },
          body: { year: 42, segment: 'frost', day, is_public: true },
        }),
      );
    const chosen = await period(first.entity_id, 3);
    await period(first.entity_id, 4);
    await period(second.entity_id, 4);
    await period(first.entity_id, 5);
    const elsewhere = await ok(owner.POST('/tenants', { body: { name: 'Other dates' } }));
    const foreign = await calendar('Foreign calendar', elsewhere.id);
    await period(foreign.entity_id, 3, elsewhere.id);
    const getScene = () => api.GET('/tenants/{tenant_id}/scenes/{scene_id}', { params: { path } });
    const setPeriod = async (period_entity_id: string | null) => {
      const current = await getScene();
      await ok(
        api.PATCH('/tenants/{tenant_id}/scenes/{scene_id}', {
          params: { path, header: { 'if-match': current.response.headers.get('etag') as string } },
          body: { period_entity_id },
        }),
      );
    };
    const periods = () =>
      ok(
        api.GET('/tenants/{tenant_id}/calendar-periods', {
          params: { path: { tenant_id: tenant.id } },
        }),
      );
    const count = (await periods()).total;
    const draft = page.getByRole('textbox', { name: 'Manuscript', exact: true });
    const source = 'On 3 **Frost** 42 she recalled 4 Frost 42. `5 Frost 42`';
    await draft.fill(source);
    await page.getByText('Details', { exact: true }).click();
    await page.getByText('Suggested period', { exact: true }).click();
    const check = page.getByRole('button', { name: 'Check dates', exact: true });
    const add = page.getByRole('button', {
      name: 'Set period to 3 Frost 42 (Coast reckoning)',
      exact: true,
    });
    await check.click();
    await expect(add).toBeVisible();
    await expect(page.getByText(/Several periods share the name 4 Frost 42/)).toBeVisible();
    await expect(page.getByRole('button', { name: /Set period to 5 Frost/ })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /Foreign calendar/ })).toHaveCount(0);
    expect((await ok(getScene())).period_entity_id).toBeNull();
    expect((await periods()).total).toBe(count);
    await draft.fill(`${source} Tomorrow.`);
    await add.click();
    await expect(page.getByText('The draft changed. Check dates again.')).toBeVisible();
    await check.click();
    await setPeriod(chosen.entity_id);
    await add.click();
    await expect(page.getByText('The Scene changed. Check dates again.')).toBeVisible();
    await check.click();
    await expect(
      page.getByText('This Scene already has a period. Use Period to change it.'),
    ).toBeVisible();
    await expect(add).toHaveCount(0);
    await setPeriod(null);
    await check.click();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await add.click();
    await expect(page.getByText('Period: 3 Frost 42', { exact: true })).toBeVisible();
    expect((await ok(getScene())).period_entity_id).toBe(chosen.entity_id);
    await expect(draft).toHaveValue(`${source} Tomorrow.`);
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();
    await page.reload();
    await page.getByText('Details', { exact: true }).click();
    await expect(page.getByText('Period: 3 Frost 42', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Clear period', exact: true }).click();
    await expect(page.getByText('Period: 3 Frost 42', { exact: true })).toHaveCount(0);
    expect((await ok(getScene())).period_entity_id).toBeNull();
    expect((await periods()).total).toBe(count);
  } finally {
    await context.close();
  }
});
for (const variant of ['draft', 'placed', 'nested', 'parent']) {
  const depth = variant === 'draft' ? 0 : variant === 'placed' ? 1 : 3;
  const placed = depth > 0;
  const hasChildren = variant === 'parent';
  test(`copied manuscripts review updates (${variant}), protect unsaved drafts and preserve session credit`, async ({
    browser,
  }) => {
    test.setTimeout(120000);
    const { owner, api, tenant, page, context } = await world(browser);
    try {
      const repository = await ok(
        owner.POST('/tenants', { body: { name: 'River stories', kind: 'repository' } }),
      );
      const chapter = await ok(
        owner.POST('/tenants/{tenant_id}/writing/chapters', {
          params: { path: { tenant_id: repository.id } },
          body: { name: 'Copied crossing' },
        }),
      );
      await ok(
        owner.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
          params: { path: { tenant_id: repository.id, entity_id: chapter.id } },
          body: {
            title: 'Manuscript',
            type: 'manuscript',
            content: 'The original crossing.',
            locale: 'en',
            is_public: true,
          },
        }),
      );
      if (placed) {
        const book = await ok(
          owner.POST('/tenants/{tenant_id}/writing/books', {
            params: { path: { tenant_id: repository.id } },
            body: { name: 'Collected crossings' },
          }),
        );
        let edition = await ok(
          owner.GET('/tenants/{tenant_id}/writing/entries/{id}', {
            params: { path: { tenant_id: repository.id, id: book.editions[0].id } },
          }),
        );
        for (let level = 1; level < depth; level++) {
          const parent = await ok(
            owner.POST('/tenants/{tenant_id}/writing/chapters', {
              params: { path: { tenant_id: repository.id } },
              body: { name: `Part ${level}` },
            }),
          );
          await ok(
            owner.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
              params: {
                path: { tenant_id: repository.id, id: edition.id },
                header: { 'if-match': edition.version },
              },
              body: { elements: [parent.id] },
            }),
          );
          edition = parent;
        }
        await ok(
          owner.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
            params: {
              path: { tenant_id: repository.id, id: edition.id },
              header: { 'if-match': edition.version },
            },
            body: { elements: [chapter.id] },
          }),
        );
      }
      if (hasChildren) {
        const child = await ok(
          owner.POST('/tenants/{tenant_id}/writing/chapters', {
            params: { path: { tenant_id: repository.id } },
            body: { name: 'Child passage' },
          }),
        );
        await ok(
          owner.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
            params: { path: { tenant_id: repository.id, entity_id: child.id } },
            body: {
              title: 'Manuscript',
              type: 'manuscript',
              content: 'Child stays here.',
              locale: 'en',
              is_public: true,
            },
          }),
        );
        const parent = await ok(
          owner.GET('/tenants/{tenant_id}/writing/entries/{id}', {
            params: { path: { tenant_id: repository.id, id: chapter.id } },
          }),
        );
        await ok(
          owner.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
            params: {
              path: { tenant_id: repository.id, id: chapter.id },
              header: { 'if-match': parent.version },
            },
            body: { elements: [...parent.elements.map((item) => item.id), child.id] },
          }),
        );
      }
      await ok(
        owner.PUT('/tenants/{tenant_id}/subscribers/{subscriber_tenant_id}', {
          params: { path: { tenant_id: repository.id, subscriber_tenant_id: tenant.id } },
        }),
      );
      await ok(
        owner.PUT('/tenants/{tenant_id}/published', {
          params: { path: { tenant_id: repository.id } },
        }),
      );
      await ok(
        owner.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
          params: { path: { tenant_id: tenant.id, repository_id: repository.id } },
        }),
      );
      const entries = await ok(
        api.GET('/tenants/{tenant_id}/entities', {
          params: { path: { tenant_id: tenant.id }, query: { q: 'Copied crossing' } },
        }),
      );
      const local = entries.items[0].id;
      await page.goto(`/?tenant=${tenant.id}&entry=${local}`);
      const draft = page.getByRole('textbox', { name: 'Manuscript', exact: true });
      await expect(draft).toHaveValue('The original crossing.', { timeout: 15000 });
      await page.getByText('Details', { exact: true }).click();
      await page.getByText('Repository comparison', { exact: true }).click();
      const compare = page.getByRole('button', { name: 'Compare saved writing', exact: true });
      await compare.click();
      await expect(
        page.getByText('The saved writing still matches the original copy.'),
      ).toBeVisible();
      const source = await ok(
        owner.GET('/tenants/{tenant_id}/entities/{entity_id}', {
          params: { path: { tenant_id: repository.id, entity_id: chapter.id } },
        }),
      );
      const payload = source.information.find((i) => i.type === 'manuscript')?.payloads[0];
      if (!payload) throw new Error('No source manuscript');
      await ok(
        owner.PATCH('/tenants/{tenant_id}/payloads/{payload_id}', {
          params: {
            path: { tenant_id: repository.id, payload_id: payload.id },
            header: { 'if-match': `W/"${payload.updated_at}"` },
          },
          body: { content: '<img src=x onerror=alert(1)> Upstream crossing.' },
        }),
      );
      await draft.fill('My saved crossing.');
      await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
      await compare.click();
      await expect(page.getByText('Both versions changed differently.')).toBeVisible();
      const review = page.locator('.repo-review-values');
      await expect(review).toContainText('The original crossing.');
      await expect(review).toContainText('My saved crossing.');
      await expect(review).toContainText('<img src=x onerror=alert(1)> Upstream crossing.');
      await expect(review.locator('img')).toHaveCount(0);
      const take = page.getByRole('button', {
        name: 'Take the update, and replace yours',
        exact: true,
      });
      await expect(take).toBeVisible();
      await expect(draft).toHaveValue('My saved crossing.');
      await page.setViewportSize({ width: 390, height: 844 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      await page.screenshot({
        path: test.info().outputPath('comparison-phone.png'),
        fullPage: true,
      });
      await page.route('**/payloads/*', (route) =>
        route.request().method() === 'PATCH' ? route.abort() : route.continue(),
      );
      await draft.fill('My unsaved crossing.');
      await take.click();
      await expect(
        page.getByText('Save your draft and resolve any conflicts before accepting an update.'),
      ).toBeVisible();
      await expect(draft).toHaveValue('My unsaved crossing.');
      await expect(page.getByRole('status', { name: 'Save status' })).toContainText(
        'Use Save now to retry.',
      );
      await page.unroute('**/payloads/*');
      await page.getByRole('button', { name: 'Save now', exact: true }).click();
      await expect(page.getByRole('status', { name: 'Save status' })).toHaveText('Saved');
      await compare.click();
      await page.getByText('Word count', { exact: true }).click();
      await page.getByText('Writing session', { exact: true }).click();
      await page.getByLabel('Session word target').fill('100');
      await page.getByRole('button', { name: 'Start session', exact: true }).click();
      await expect(page.getByText('Session progress · 0 words', { exact: true })).toBeVisible();
      await take.click();
      await expect(page.getByText('Repository writing saved.', { exact: true })).toBeVisible();
      await expect(draft).toHaveValue('<img src=x onerror=alert(1)> Upstream crossing.');
      await expect(page.getByText('Session progress · 0 words', { exact: true })).toBeVisible();
      await compare.click();
      await expect(
        page.getByText('The saved writing still matches the original copy.'),
      ).toBeVisible();
      await expect(take).toHaveCount(0);
      await page.reload();
      await expect(draft).toHaveValue('<img src=x onerror=alert(1)> Upstream crossing.');
      if (placed) {
        const saved = await ok(
          api.GET('/tenants/{tenant_id}/writing/entries/{id}', {
            params: { path: { tenant_id: tenant.id, id: local } },
          }),
        );
        expect(saved.parent_id).toBeTruthy();
        let root = saved;
        while (root.parent_id) {
          root = await ok(
            api.GET('/tenants/{tenant_id}/writing/entries/{id}', {
              params: { path: { tenant_id: tenant.id, id: root.parent_id } },
            }),
          );
        }
        await page.goto(`/?tenant=${tenant.id}&entry=${root.id}&view=read`);
        // Continuous reading fetches each nested entry before its manuscript.
        await expect(page.locator('article')).toContainText('Upstream crossing.', {
          timeout: 15000,
        });
        await expect(page.locator('article')).toContainText('Copied crossing');
        if (hasChildren)
          await expect(page.locator('article')).toHaveText(/Upstream crossing.*Child stays here/s);
      }
    } finally {
      await context.close();
    }
  });
}
