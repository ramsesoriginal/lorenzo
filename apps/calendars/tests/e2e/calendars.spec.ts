import { type Browser, expect, type Page, test } from '@playwright/test';
import { apiAs, ok, refreshTokenFor } from './support/api.ts';
import { AUTHGEAR_URL, REFRESH_TOKEN_KEY, SITE_URL, SUBJECT_COOKIE } from './support/env.ts';
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
test('the header offers the skip link, the page links and the account once signed in', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`/?tenant=${world.tenantId}`);
  await expect(page.getByRole('heading', { name: 'Calendars', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeAttached();
  const pages = page.getByRole('navigation', { name: 'Pages' });
  await expect(pages.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page');
  await expect(pages.getByRole('link', { name: 'Events' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Account' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Log out', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeHidden();
  await page.getByRole('link', { name: 'Skip to content' }).focus();
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeVisible();
  await page.context().close();
});
test('imported irregular year is browsable without creating periods, and dated information stays separate', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/periods')) writes.push(r.url());
  });
  const periods = () =>
    ok(
      world.api.GET('/tenants/{tenant_id}/calendars/{calendar_id}/periods', {
        params: {
          path: { tenant_id: world.tenantId, calendar_id: world.calendarId },
          query: { size: 100 },
        },
      }),
    );
  const before = await periods();
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await expect(page.getByRole('heading', { name: 'Isles calendar', exact: true })).toBeVisible();
  await expect(
    page.getByRole('combobox', { name: /^Month or festival/ }).locator('option'),
  ).toHaveCount(19);
  await expect(page.locator('.day')).toHaveCount(27);
  await expect(page.locator('.weekday').first()).toHaveText('Montag');
  const firstMoon = page.locator('.day').first().locator('.moon-phase').first();
  await expect(firstMoon).toHaveAttribute('title', /^Maira:/);
  await expect(firstMoon).toHaveText(/[🌑🌒🌓🌔🌕🌖🌗🌘]/u);
  await expect(page.locator('.day').first()).toHaveAttribute(
    'aria-description',
    /Maira:.*Mendra:.*Galon:/,
  );
  await page.getByRole('combobox', { name: /^Month or festival/ }).selectOption('segment-4');
  await expect(page.locator('.day')).toHaveCount(2);
  await page.getByRole('combobox', { name: /^Month or festival/ }).selectOption('segment-6');
  const diaryDay = page.getByRole('button', { name: '16 Quirm 3286', exact: true });
  await expect(diaryDay).toContainText('A lantern was lit by the harbour.');
  await expect(page.getByRole('button', { name: '17 Quirm 3286', exact: true })).toContainText(
    'Harbour storm',
  );
  await expect(page.getByRole('button', { name: '18 Quirm 3286', exact: true })).toContainText(
    'Recurring · Harbour feast',
  );
  await diaryDay.click();
  await expect(
    page.locator('aside').getByText('A lantern was lit by the harbour.', { exact: true }),
  ).toBeVisible();
  await expect(page.locator('aside .selected-moons')).toContainText('Maira:');
  await page.getByRole('button', { name: '17 Quirm 3286', exact: true }).click();
  await page.getByRole('link', { name: 'Harbour storm', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Harbour storm', exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page.getByText('A storm reaches the harbour.', { exact: true })).toBeVisible();
  await page.goBack();
  await page.getByRole('button', { name: 'Next year', exact: true }).click();
  await expect(page.getByLabel('Year', { exact: true })).toHaveValue('3287');
  await expect(page.getByRole('link', { name: /Harbour feast/ })).toBeVisible();
  expect(writes).toEqual([]);
  expect((await periods()).total).toBe(before.total);
  await page.screenshot({ path: test.info().outputPath('desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('phone-moons.png'), fullPage: true });
  await page.context().close();
});
test('authoring creates periods explicitly and edits ordered information and story-event dates', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await page.getByRole('button', { name: '2 Rimsep 3286', exact: true }).click();
  await page.getByRole('button', { name: 'Add information to this date', exact: true }).click();
  await page.getByLabel('Information title', { exact: true }).fill('Harbour log');
  await page.getByLabel('Text', { exact: true }).fill('The beacon is repaired.');
  await page.locator('input[type=file]').setInputFiles({
    name: 'beacon.png',
    mimeType: 'image/png',
    buffer: await page.screenshot(),
  });
  await page.getByRole('button', { name: 'Save information', exact: true }).click();
  await expect(page.getByText('The beacon is repaired.', { exact: true })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Harbour log', exact: true })).toBeVisible();
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await page.getByRole('button', { name: '3 Rimsep 3286', exact: true }).click();
  await page.getByText('Create a fact or story event', { exact: true }).click();
  await page.getByLabel('Entry name', { exact: true }).fill('Beacon relit');
  await page.getByRole('button', { name: 'Create dated entry', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Beacon relit', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: '3 Rimsep 3286', exact: true })).toBeVisible();
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await page.getByRole('button', { name: '4 Rimsep 3286', exact: true }).click();
  await page.getByText('Associate an existing fact or event', { exact: true }).click();
  await page.getByLabel('Find a fact or event').fill('Beacon relit');
  await page.getByRole('button', { name: 'Search entries', exact: true }).click();
  await page.getByRole('button', { name: 'Beacon relit', exact: true }).click();
  await expect(page.getByRole('link', { name: '3 Rimsep 3286', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: '4 Rimsep 3286', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Remove date association', exact: true }).last().click();
  await expect(page.getByRole('link', { name: '4 Rimsep 3286', exact: true })).toHaveCount(0);
  await page.context().close();
});
test('definition conflict retains the draft until the saved version has been reviewed', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await page.getByText('Edit calendar definition', { exact: true }).click();
  await page.getByLabel('Segment name', { exact: true }).first().fill('Rimsep draft');
  await page.getByRole('button', { name: 'Preview this year', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Save definition', exact: true })).toBeEnabled();
  const path = { tenant_id: world.tenantId, entity_id: world.calendarId };
  const response = await world.api.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
    params: { path },
  });
  const saved = await ok(Promise.resolve(response));
  const second = saved.definition.segments[1];
  if (!second) throw new Error('Missing fixture segment');
  second.name = 'Sogmen upstream';
  await ok(
    world.api.PUT('/tenants/{tenant_id}/calendars/{entity_id}/definition', {
      params: { path, header: { 'if-match': response.response.headers.get('etag') ?? '' } },
      body: saved.definition,
    }),
  );
  await page.getByRole('button', { name: 'Save definition', exact: true }).click();
  await expect(page.getByText(/Someone changed this calendar/)).toBeVisible();
  await expect(page.getByLabel('Segment name', { exact: true }).first()).toHaveValue(
    'Rimsep draft',
  );
  await expect(page.getByRole('button', { name: 'Save definition', exact: true })).toBeDisabled();
  await expect(page.locator('pre')).toContainText('Sogmen upstream');
  await page
    .getByRole('button', { name: 'I reviewed it; keep my draft against this version', exact: true })
    .click();
  await page.getByRole('button', { name: 'Preview this year', exact: true }).click();
  await page.getByRole('button', { name: 'Save definition', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Rimsep draft', exact: true })).toBeVisible();
  await page.context().close();
});
test('readers see permitted names and dates without private information or author controls', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.readerSubject);
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await page.getByRole('combobox', { name: /^Month or festival/ }).selectOption('segment-6');
  await expect(page.getByRole('button', { name: '16 Quirm 3286', exact: true })).toContainText(
    'A lantern was lit by the harbour.',
  );
  await expect(page.getByRole('button', { name: '17 Quirm 3286', exact: true })).toContainText(
    'Harbour storm',
  );
  await expect(page.getByText('A storm reaches the harbour.', { exact: true })).toHaveCount(0);
  await expect(page.getByText(/Secret tide|Hidden landing|Secret rite/)).toHaveCount(0);
  await page.getByRole('button', { name: '17 Quirm 3286', exact: true }).click();
  await page.getByRole('link', { name: 'Harbour storm', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Harbour storm', exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page.getByText('A storm reaches the harbour.', { exact: true })).toHaveCount(0);
  await expect(page.getByText('No information is available to you here.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add information', exact: true })).toHaveCount(1);
  await page.context().close();
});
test('a calendar can be created through structured preview and opened on a phone after PKCE login', async ({
  browser,
}) => {
  const world = await buildWorld();
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await context.addCookies([{ name: SUBJECT_COOKIE, value: world.subject, url: AUTHGEAR_URL }]);
  const page = await context.newPage();
  await page.goto(`/?tenant=${world.tenantId}`);
  await page.getByRole('button', { name: 'Log in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Calendars', exact: true })).toBeVisible();
  await page.getByText('Create a calendar', { exact: true }).click();
  await page.getByLabel('Calendar name', { exact: true }).fill('Tide reckoning');
  await page.getByLabel('Segment name', { exact: true }).fill('High tide');
  await page.getByLabel('Days', { exact: true }).fill('12');
  await page.getByLabel('Preview year', { exact: true }).fill('9');
  await page.getByRole('button', { name: 'Preview this year', exact: true }).click();
  await page.getByRole('button', { name: 'Create calendar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Tide reckoning', exact: true })).toBeVisible();
  await expect(page.locator('.day')).toHaveCount(12);
  const overflow = await page.evaluate(() =>
    Array.from(document.querySelectorAll('body *'))
      .filter((e) => e.getBoundingClientRect().right > innerWidth + 1)
      .map((e) => ({ tag: e.tagName, cls: e.className, width: e.getBoundingClientRect().width })),
  );
  expect(overflow).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('phone.png'), fullPage: true });
  await context.close();
});

test('recurring observance creation and rule edits do not materialize occurrences', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  const periods = () =>
    ok(
      world.api.GET('/tenants/{tenant_id}/calendars/{calendar_id}/periods', {
        params: {
          path: { tenant_id: world.tenantId, calendar_id: world.calendarId },
          query: { size: 100 },
        },
      }),
    );
  const before = await periods();
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await page.getByRole('button', { name: '5 Rimsep 3286', exact: true }).click();
  await page.getByText('Create a recurring observance', { exact: true }).click();
  await page.getByLabel('Observance name', { exact: true }).fill('Lantern feast');
  await page.getByLabel('Every N years', { exact: true }).fill('3');
  await page.locator('aside').getByLabel('Year offset', { exact: true }).fill('1');
  await page.getByRole('button', { name: 'Create recurring observance', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Lantern feast', exact: true })).toBeVisible();
  await page.getByText('Edit recurrence', { exact: true }).click();
  await page.getByLabel('Day', { exact: true }).fill('6');
  await page.getByRole('button', { name: 'Save recurrence', exact: true }).click();
  await expect(page.getByText(/6 Rimsep, every 3 year/)).toBeVisible();
  expect((await periods()).total).toBe(before.total);
  await page.context().close();
});

test('home recovers from a deleted remembered library without substituting explicit URLs', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  await page.addInitScript(() =>
    localStorage.setItem('lorenzo:lastTenant', '00000000-0000-0000-0000-000000000001'),
  );
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Calendars', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Isles calendar', exact: true })).toBeVisible();
  await page.goto('/?tenant=00000000-0000-0000-0000-000000000001');
  await expect(page.getByText(/This library is not available to this account/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Isles calendar', exact: true })).toHaveCount(0);
  await page.context().close();
});

// The shared header remains usable before authentication and at phone widths.
test('signed-out welcome and appearance controls work in light and dark themes', async ({
  browser,
}) => {
  const context = await browser.newContext({
    colorScheme: 'light',
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage();
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Calendars', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeVisible();
  // At phone width the header shows the spark alone (identity 12.2); the lockup is for wider screens.
  await expect(page.locator('.brand-spark')).toBeVisible();
  await expect(page.locator('.brand-mark--light')).toBeHidden();
  expect(
    await page.locator('.brand-spark').evaluate((node) => (node as HTMLImageElement).naturalWidth),
  ).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.brand-spark')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Light theme', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('welcome-dark-phone.png'), fullPage: true });
  await page.getByRole('button', { name: 'Light theme', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.locator('.brand-spark')).toBeHidden();
  await expect(page.locator('.brand-mark--light')).toBeVisible();
  expect(
    await page
      .locator('.brand-mark--light')
      .evaluate((node) => (node as HTMLImageElement).naturalWidth),
  ).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click();
  await expect(page.locator('.brand-mark--dark')).toBeVisible();
  expect(
    await page
      .locator('.brand-mark--dark')
      .evaluate((node) => (node as HTMLImageElement).naturalWidth),
  ).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Light theme', exact: true }).click();
  await page.screenshot({
    path: test.info().outputPath('welcome-light-desktop.png'),
    fullPage: true,
  });
  await context.close();
});

test('month content is cached and moon names remain available when selecting a day on a phone', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  await page.setViewportSize({ width: 1280, height: 900 });
  const reads: string[] = [];
  page.on('request', (r) => {
    if (r.method() === 'GET' && /\/(information|entries)\?/.test(r.url())) reads.push(r.url());
  });
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await page.getByRole('combobox', { name: /^Month or festival/ }).selectOption('segment-6');
  await expect(page.locator('.day-content').filter({ hasText: 'Loading notes' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '16 Quirm 3286', exact: true })).toContainText(
    'A lantern was lit by the harbour.',
  );
  const loaded = reads.length;
  await page.getByRole('combobox', { name: /^Month or festival/ }).selectOption('segment-4');
  await page.getByRole('combobox', { name: /^Month or festival/ }).selectOption('segment-6');
  await expect(page.getByRole('button', { name: '16 Quirm 3286', exact: true })).toContainText(
    'A lantern was lit by the harbour.',
  );
  expect(reads.length).toBe(loaded);
  await page.screenshot({
    path: test.info().outputPath('month-content-desktop.png'),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '16 Quirm 3286', exact: true }).click();
  await expect(page.locator('aside .selected-moons')).toContainText('Maira:');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('month-notes-phone.png'), fullPage: true });
  await page.context().close();
});

test('whole year reuses month content and supports keyboard tabs, festivals and leap years without writes', async ({
  browser,
}) => {
  const world = await buildWorld();
  const path = { tenant_id: world.tenantId, entity_id: world.calendarId };
  const response = await world.api.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
    params: { path },
  });
  const saved = await ok(Promise.resolve(response));
  saved.definition.segments[3].kind = 'festival';
  saved.definition.segments[3].in_week = false;
  saved.definition.segments[18].when = { every: 4, offset: 2 };
  await ok(
    world.api.PUT('/tenants/{tenant_id}/calendars/{entity_id}/definition', {
      params: { path, header: { 'if-match': response.response.headers.get('etag') ?? '' } },
      body: saved.definition,
    }),
  );
  const page = await signedIn(browser, world.subject);
  await page.setViewportSize({ width: 1280, height: 900 });
  const writes: string[] = [];
  const reads: string[] = [];
  page.on('request', (request) => {
    if (request.method() !== 'GET' && request.url().includes('/tenants/'))
      writes.push(request.url());
    if (request.method() === 'GET' && /\/(information|entries)\?/.test(request.url()))
      reads.push(request.url());
  });
  const periods = () =>
    ok(
      world.api.GET('/tenants/{tenant_id}/calendars/{calendar_id}/periods', {
        params: {
          path: { tenant_id: world.tenantId, calendar_id: world.calendarId },
          query: { size: 100 },
        },
      }),
    );
  const before = await periods();
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await page.getByRole('combobox', { name: /^Month or festival/ }).selectOption('segment-6');
  await expect(page.getByRole('button', { name: '16 Quirm 3286', exact: true })).toContainText(
    'A lantern was lit',
  );
  await page.getByRole('tab', { name: 'Month or festival', exact: true }).press('End');
  const yearPanel = page.getByRole('tabpanel', { name: 'Whole year', exact: true });
  await expect(page.getByRole('tab', { name: 'Whole year', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(yearPanel.locator('.year-segment > h2')).toHaveText(
    saved.definition.segments.map((segment) => segment.name),
  );
  await expect(yearPanel.locator('.day')).toHaveCount(387);
  await expect(yearPanel.locator('.festival .day')).toHaveCount(2);
  await expect(page.getByRole('button', { name: '16 Quirm 3286', exact: true })).toContainText(
    'A lantern was lit',
  );
  await expect(page.getByRole('button', { name: '17 Quirm 3286', exact: true })).toContainText(
    'Harbour storm',
  );
  await expect(page.getByRole('button', { name: '18 Quirm 3286', exact: true })).toContainText(
    'Recurring · Harbour feast',
  );
  await expect(yearPanel.locator('.day-content').filter({ hasText: 'Loading notes' })).toHaveCount(
    0,
  );
  const loaded = reads.length;
  await page.getByRole('tab', { name: 'Whole year', exact: true }).press('Home');
  await expect(page.getByRole('combobox', { name: /^Month or festival/ })).toHaveValue('segment-6');
  await page.getByRole('tab', { name: 'Month or festival', exact: true }).press('ArrowRight');
  await expect(yearPanel.locator('.day-content').filter({ hasText: 'Loading notes' })).toHaveCount(
    0,
  );
  expect(reads.length).toBe(loaded);
  await page.screenshot({ path: test.info().outputPath('whole-year-desktop.png') });
  await page.getByRole('button', { name: 'Next year', exact: true }).click();
  await expect(page.getByLabel('Year', { exact: true })).toHaveValue('3287');
  await expect(page.getByRole('tab', { name: 'Whole year', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(yearPanel.locator('.year-segment')).toHaveCount(18);
  await expect(yearPanel.locator('.day')).toHaveCount(386);
  await page.reload();
  await expect(page.getByRole('tab', { name: 'Whole year', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(yearPanel.locator('.day')).toHaveCount(386);
  expect((await periods()).total).toBe(before.total);
  expect(writes).toEqual([]);
  await page.context().close();
});

test('whole year on a phone keeps reader visibility and returns from day detail to the selected date', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.readerSubject);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286&view=year`);
  const panel = page.getByRole('tabpanel', { name: 'Whole year', exact: true });
  await expect(panel.locator('.day')).toHaveCount(387);
  await expect(panel.locator('.day-content').filter({ hasText: 'Loading notes' })).toHaveCount(0);
  await expect(
    page.getByText(/Secret tide|Hidden landing|Secret rite|A storm reaches/),
  ).toHaveCount(0);
  const day = page.getByRole('button', { name: '16 Quirm 3286', exact: true });
  await expect(day).toContainText('A lantern was lit');
  await day.click();
  await expect(
    page.locator('aside').getByText('A lantern was lit by the harbour.', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Back to calendar', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Back to calendar', exact: true }).click();
  await expect(day).toBeFocused();
  await expect(day).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('whole-year-phone.png') });
  await page.getByRole('tab', { name: 'Month or festival', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Back to calendar', exact: true })).toHaveCount(0);
  await expect(page.locator('.day')).toHaveCount(27);
  await page.context().close();
});

test('Event order shows evidence, keeps conflicting selections, and stays absent for readers', async ({
  browser,
}) => {
  const world = await buildWorld();
  async function event(name: string) {
    return ok(
      world.api.POST('/tenants/{tenant_id}/entities', {
        params: { path: { tenant_id: world.tenantId } },
        body: { name, kinds: ['event'], parents: [] },
      }),
    );
  }
  const first = await event('The bell rings');
  const second = await event('The gates close');
  const third = await event('The flight begins');
  // The reader can read this Event, but private relationships remain undisclosed.
  await ok(
    world.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: {
        path: { tenant_id: world.tenantId, entity_id: first.id },
        header: { 'if-match': `W/"${first.updated_at}"` },
      },
      body: { is_public: true },
    }),
  );
  const page = await signedIn(browser, world.subject);
  await page.goto(`/entry/?tenant=${world.tenantId}&id=${first.id}`);
  const panel = page.locator('[data-event-order]');
  await panel.getByText('Order and causes', { exact: true }).click();
  await panel.getByLabel('Find an Event').fill('The gates');
  await panel.getByRole('button', { name: 'Search Events', exact: true }).click();
  await panel.getByRole('button', { name: second.name, exact: true }).click();
  await panel.getByRole('button', { name: 'Compare Events', exact: true }).click();
  await expect(panel).toContainText('Linearized · no recorded ordering path');
  await panel.getByLabel('Relationship', { exact: true }).selectOption('causes');
  await panel.getByRole('button', { name: 'Add relationship', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText('Relationship recorded.');
  await panel.getByRole('button', { name: 'Compare Events', exact: true }).click();
  await expect(panel).toContainText('Causal · a recorded chain of causes');
  await expect(panel).toContainText('The bell rings caused The gates close');
  await panel.getByLabel('Find an Event').fill('The flight');
  await panel.getByRole('button', { name: 'Search Events', exact: true }).click();
  await panel.getByRole('button', { name: third.name, exact: true }).click();
  // Another editor changes the first Event's order after this page read its version.
  const path = { tenant_id: world.tenantId, event_id: first.id };
  const saved = await world.api.GET('/tenants/{tenant_id}/events/{event_id}/relationships', {
    params: { path },
  });
  await ok(
    world.api.PUT('/tenants/{tenant_id}/events/{event_id}/relationships/{other_event_id}', {
      params: {
        path: { ...path, other_event_id: third.id },
        header: { 'if-match': saved.response.headers.get('etag') ?? '' },
      },
      body: { kind: 'order', direction: 'outgoing' },
    }),
  );
  await panel.getByRole('button', { name: 'Add relationship', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Your selection is kept');
  await expect(panel.getByText(`Selected Event: ${third.name}`, { exact: true })).toBeVisible();
  await panel.getByRole('button', { name: 'Refresh saved relationships', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Saved relationships refreshed');
  await panel.getByLabel('Relationship', { exact: true }).selectOption('before');
  await panel.getByRole('button', { name: 'Add relationship', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText('Relationship recorded.');
  await panel.getByRole('button', { name: 'Compare Events', exact: true }).click();
  await expect(panel).toContainText('Ruled · recorded ordering');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('event-order-phone.png') });
  await panel.getByRole('button', { name: 'Remove', exact: true }).last().click();
  await expect(panel.getByRole('status')).toHaveText('Relationship removed.');
  const reader = await signedIn(browser, world.readerSubject);
  const graphRequests: string[] = [];
  reader.on('request', (r) => {
    if (r.url().includes('/relationships') || r.url().includes('/events/compare'))
      graphRequests.push(r.url());
  });
  await reader.goto(`/entry/?tenant=${world.tenantId}&id=${first.id}`);
  await expect(
    reader.getByRole('heading', { name: first.name, exact: true, level: 1 }),
  ).toBeVisible();
  await expect(reader.locator('[data-event-order]')).toHaveCount(1);
  await reader.locator('[data-event-order] summary').click();
  await expect(
    reader.getByText('No shared relationships are available in your view.'),
  ).toBeVisible();
  await expect(reader.getByRole('button', { name: 'Add relationship', exact: true })).toHaveCount(
    0,
  );
  expect(graphRequests.filter((url) => url.includes('/relationships'))).toHaveLength(1);
  await page.context().close();
  await reader.context().close();
});

test('standalone Events can be found by participating being without acquiring a date', async ({
  browser,
}) => {
  const world = await buildWorld();
  const being = await ok(
    world.api.POST('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id: world.tenantId } },
      body: { name: 'Aster the traveller', kinds: ['being'], parents: [] },
    }),
  );
  const page = await signedIn(browser, world.subject);
  await page.goto(`/events/?tenant=${world.tenantId}`);
  await page.getByText('Create an Event', { exact: true }).click();
  await page.getByLabel('Event name', { exact: true }).fill('The beacon is lit');
  await page.getByRole('button', { name: 'Create Event', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'The beacon is lit', exact: true, level: 1 }),
  ).toBeVisible();
  const eventId = new URL(page.url()).searchParams.get('id');
  if (!eventId) throw new Error('Created Event address is missing.');
  const roster = page.locator('[data-participants]');
  await roster.getByText('Participating beings', { exact: true }).click();
  await roster.getByLabel('Find a participating being', { exact: true }).fill('Aster');
  await roster.getByRole('button', { name: 'Search beings', exact: true }).click();
  await roster.getByRole('button', { name: being.name, exact: true }).click();
  await roster.getByRole('button', { name: 'Add participant', exact: true }).click();
  await expect(roster.getByText('Participation recorded.', { exact: true })).toBeVisible();
  const dates = await ok(
    world.api.GET('/tenants/{tenant_id}/entities/{entity_id}/dates', {
      params: { path: { tenant_id: world.tenantId, entity_id: eventId } },
    }),
  );
  expect(dates).toEqual([]);
  await page.getByRole('link', { name: 'All Events', exact: true }).click();
  await page.getByText('Participants and causes', { exact: true }).click();
  await page.getByLabel('Filter by being', { exact: true }).fill('Aster');
  await page.getByRole('button', { name: 'Search beings', exact: true }).click();
  await page.getByRole('button', { name: being.name, exact: true }).click();
  await expect(page.locator('[data-event-list] > li')).toHaveCount(1);
  await expect(page.locator('[data-event-list]')).toContainText('The beacon is lit');
  await page.getByRole('combobox', { name: 'List order', exact: true }).selectOption('order');
  await page.getByRole('button', { name: 'Find Events', exact: true }).click();
  await expect(page.getByText('1 Event.', { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('link', { name: 'The beacon is lit', exact: true }).click();
  await page
    .locator('[data-participants]')
    .getByText('Participating beings', { exact: true })
    .click();
  await page
    .locator('[data-participants]')
    .getByRole('button', { name: 'Remove participant', exact: true })
    .click();
  await expect(page.getByText('Participation removed.', { exact: true })).toBeVisible();
  const reader = await signedIn(browser, world.readerSubject);
  await reader.goto(`/events/?tenant=${world.tenantId}`);
  await expect(
    reader.getByRole('heading', { name: 'Events', exact: true, level: 1 }),
  ).toBeVisible();
  await expect(reader.getByText('Participants and causes', { exact: true })).toHaveCount(0);
  await expect(reader.getByText('Create an Event', { exact: true })).toHaveCount(1);
  await expect(reader.getByRole('link', { name: 'The beacon is lit', exact: true })).toHaveCount(0);
  await page.context().close();
  await reader.context().close();
});

test('calendar addresses and named or numbered date links preserve identity without creating dates', async ({
  browser,
}) => {
  const world = await buildWorld();
  const path = { tenant_id: world.tenantId, entity_id: world.calendarId };
  await ok(
    world.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/slug', {
      params: { path },
      body: { slug: 'reckoning' },
    }),
  );
  const event = await ok(
    world.api.POST('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id: world.tenantId } },
      body: { name: 'A date remembered', kinds: ['event'], parents: [], slug: 'arrival' },
    }),
  );
  await ok(
    world.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { tenant_id: world.tenantId, entity_id: event.id } },
      body: {
        title: 'Dates',
        is_public: false,
        locale: 'en',
        type: 'note',
        content:
          '[[calendar/reckoning]] {{cal reckoning 3286/Quirm/16}} {{cal reckoning 3286/6/16}} {{cal missing 0}}',
      },
    }),
  );
  const page = await signedIn(browser, world.subject);
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/periods')) writes.push(r.url());
  });
  await page.goto(`/calendar/?tenant=${world.tenantId}&id=${world.calendarId}&year=3286`);
  await expect(page).toHaveURL(/slug=reckoning/);
  await page.goto(`/entry/?tenant=${world.tenantId}&id=arrival`);
  await expect(
    page.getByRole('heading', { name: event.name, exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page).toHaveURL(/slug=arrival/);
  await expect(page.locator('a.ls-cal')).toHaveCount(2);
  await expect(page.locator('a.ls-cal').first()).toHaveText('16 Quirm 3286');
  await page.locator('a.ls-cal').first().click();
  await expect(page.getByRole('combobox', { name: /^Month or festival/ })).toHaveValue('segment-6');
  await expect(
    page.locator('aside').getByRole('heading', { name: '16 Quirm 3286', exact: true }),
  ).toBeVisible();
  expect(writes).toEqual([]);
  await page.goto(`/entry/?tenant=${world.tenantId}&slug=arrival`);
  await page.getByText('Name, link name and audience', { exact: true }).click();
  await page.getByLabel('Link name', { exact: true }).fill(event.id);
  await page.getByRole('button', { name: 'Save link name', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`slug=${event.id}`));
  await expect(
    page.getByRole('heading', { name: event.name, exact: true, level: 1 }),
  ).toBeVisible();
  await page.goto(`/entry/?tenant=${world.tenantId}&id=${event.id}`);
  await expect(page).toHaveURL(new RegExp(`slug=${event.id}`));
  await page.context().close();
});

test('prefetched Event information survives in-app navigation only after fresh access and stays out of storage', async ({
  browser,
}) => {
  const world = await buildWorld();
  const tenant_id = world.tenantId;
  const author = await apiAs(`calendar-other-author-${crypto.randomUUID()}`);
  const me = await ok(author.GET('/me'));
  await ok(
    world.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id } },
      body: { user_id: me.id, role: 'author' },
    }),
  );
  const event = await ok(
    author.POST('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id } },
      body: {
        name: 'A private departure',
        slug: 'private-departure',
        kinds: ['event'],
        parents: [],
      },
    }),
  );
  await ok(
    author.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { tenant_id, entity_id: event.id } },
      body: {
        title: 'Private record',
        type: 'note',
        content: 'Private cache marker',
        is_public: false,
        locale: 'en',
      },
    }),
  );
  const page = await signedIn(browser, world.subject);
  let entityReads = 0;
  let capabilityReads = 0;
  const writes: string[] = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() === 'GET' && path.endsWith(`/entities/${event.id}`)) entityReads++;
    if (path.endsWith('/events/access')) capabilityReads++;
    if (request.method() !== 'GET' && path.startsWith(`/tenants/${tenant_id}/`)) writes.push(path);
  });
  await page.goto(`/events/?tenant=${tenant_id}`);
  const open = page.getByRole('link', { name: event.name, exact: true });
  await expect(open).toBeVisible();
  await page.evaluate(() => Reflect.set(window, 'calendarNavigationMarker', 'same document'));
  const prefetched = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith(`/entities/${event.id}`),
  );
  await open.hover();
  await (await prefetched).finished();
  await open.click();
  await expect(page.getByText('Private cache marker', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => Reflect.get(window, 'calendarNavigationMarker'))).toBe(
    'same document',
  );
  expect(entityReads).toBe(1);
  expect(capabilityReads).toBeGreaterThanOrEqual(2);
  expect(
    await page.evaluate(() =>
      [localStorage, sessionStorage].some((store) =>
        Object.values(store).some((value) => String(value).includes('Private cache marker')),
      ),
    ),
  ).toBe(false);
  const campaigns = await ok(
    world.api.GET('/tenants/{tenant_id}/campaigns', { params: { path: { tenant_id } } }),
  );
  const campaign = campaigns.items[0];
  if (!campaign) throw new Error('Missing fixture campaign.');
  await ok(
    world.api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out', {
      params: { path: { tenant_id, campaign_id: campaign.id } },
    }),
  );
  await page.getByRole('link', { name: 'All Events', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Events', exact: true, level: 1 })).toBeVisible();
  await expect(page.getByRole('link', { name: event.name, exact: true })).toHaveCount(0);
  await page.goBack();
  await expect(page.getByText('Private cache marker', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: event.name, exact: true, level: 1 })).toHaveCount(
    0,
  );
  expect(writes).toEqual([]);
  await page.context().close();
});

test('a write finishing after leaving an Event does not reload the new view', async ({
  browser,
}) => {
  const world = await buildWorld();
  const path = { tenant_id: world.tenantId };
  const event = await ok(
    world.api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Before departure', kinds: ['event'], parents: [] },
    }),
  );
  const page = await signedIn(browser, world.subject);
  await page.goto(`/entry/?tenant=${world.tenantId}&id=${event.id}`);
  await page.getByText('Name, link name and audience', { exact: true }).click();
  await page.getByLabel('Entry name', { exact: true }).fill('After departure');
  const started = Promise.withResolvers<void>();
  const release = Promise.withResolvers<void>();
  await page.route(`**/entities/${event.id}`, async (route) => {
    if (route.request().method() === 'PATCH') {
      started.resolve();
      await release.promise;
    }
    await route.continue();
  });
  await page.evaluate(() => Reflect.set(window, 'pendingWriteMarker', 'still here'));
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      new URL(response.url()).pathname.endsWith(`/entities/${event.id}`),
  );
  await page.getByRole('button', { name: 'Save name', exact: true }).click();
  await started.promise;
  try {
    await page.getByRole('link', { name: 'All Events', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Before departure', exact: true })).toBeVisible();
  } finally {
    release.resolve();
  }
  await (await saved).finished();
  await expect
    .poll(
      async () =>
        (
          await ok(
            world.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: { ...path, entity_id: event.id } },
            }),
          )
        ).name,
    )
    .toBe('After departure');
  await expect(page.getByRole('heading', { name: 'Events', exact: true, level: 1 })).toBeVisible();
  expect(await page.evaluate(() => Reflect.get(window, 'pendingWriteMarker'))).toBe('still here');
  await page.context().close();
});

for (const preferred of ['dark', 'light'] as const) {
  test(`explicit ${preferred} appearance choice survives navigation, history and reloads`, async ({
    browser,
  }) => {
    const world = await buildWorld();
    const page = await signedIn(browser, world.subject);
    await page.emulateMedia({ colorScheme: preferred === 'dark' ? 'light' : 'dark' });
    await page.goto(`/?tenant=${world.tenantId}`);
    await expect(page.getByRole('link', { name: 'Isles calendar', exact: true })).toBeVisible();
    await page
      .getByRole('button', {
        name: preferred === 'dark' ? 'Dark theme' : 'Light theme',
        exact: true,
      })
      .click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', preferred);
    await page.getByRole('link', { name: 'Isles calendar', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: 'Isles calendar', exact: true, level: 1 }),
    ).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', preferred);
    await page.goBack();
    await expect(
      page.getByRole('heading', { name: 'Calendars', exact: true, level: 1 }),
    ).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', preferred);
    await page.goForward();
    await expect(
      page.getByRole('heading', { name: 'Isles calendar', exact: true, level: 1 }),
    ).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', preferred);
    await page.reload();
    await expect(
      page.getByRole('heading', { name: 'Isles calendar', exact: true, level: 1 }),
    ).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', preferred);
    await expect(
      page.getByRole('button', {
        name: preferred === 'dark' ? 'Light theme' : 'Dark theme',
        exact: true,
      }),
    ).toHaveAttribute('aria-pressed', String(preferred === 'dark'));
    await page.context().close();
  });
}

test('appearance choice survives page swaps when preference storage is unavailable', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  await page.emulateMedia({ colorScheme: 'light' });
  await page.addInitScript(() => {
    const get = Storage.prototype.getItem;
    const set = Storage.prototype.setItem;
    Storage.prototype.getItem = function (key) {
      if (key === 'lorenzo:calendars:theme')
        throw new DOMException('Storage unavailable', 'SecurityError');
      return get.call(this, key);
    };
    Storage.prototype.setItem = function (key, value) {
      if (key === 'lorenzo:calendars:theme')
        throw new DOMException('Storage unavailable', 'SecurityError');
      set.call(this, key, value);
    };
  });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(`/?tenant=${world.tenantId}`);
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click();
  await page.getByRole('link', { name: 'Isles calendar', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Isles calendar', exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('button', { name: 'Light theme', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  expect(errors).toEqual([]);
  await page.context().close();
});

test('learning is explicit, versioned and separate from Information audiences', async ({
  browser,
}) => {
  const world = await buildWorld();
  const path = { tenant_id: world.tenantId };
  const create = (name: string, kinds: ('event' | 'being' | 'fact')[]) =>
    ok(
      world.api.POST('/tenants/{tenant_id}/entities', {
        params: { path },
        body: { name, kinds, parents: [] },
      }),
    );
  const event = await create('Prisoner interrogation', ['event']);
  const being = await create('Mara', ['being']);
  const fact = await create('Hidden passage', ['fact']);
  const info = await ok(
    world.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { ...path, entity_id: fact.id } },
      body: {
        title: 'Waterfall entrance',
        locale: 'en',
        type: 'note',
        content: 'Behind the waterfall.',
        is_public: false,
      },
    }),
  );
  const eventPath = { ...path, event_id: event.id };
  const participants = await world.api.GET('/tenants/{tenant_id}/events/{event_id}/participants', {
    params: { path: eventPath },
  });
  await ok(
    world.api.PUT('/tenants/{tenant_id}/events/{event_id}/participants/{being_id}', {
      params: {
        path: { ...eventPath, being_id: being.id },
        header: { 'if-match': participants.response.headers.get('etag') ?? '' },
      },
    }),
  );
  const audience = () =>
    ok(
      world.api.GET('/tenants/{tenant_id}/information/{information_id}/audience', {
        params: { path: { ...path, information_id: info.id } },
      }),
    );
  const before = await audience();
  const outer = await world.api.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
    params: { path: { ...path, entity_id: event.id } },
  });
  await ok(
    world.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: {
        path: { ...path, entity_id: event.id },
        header: { 'if-match': outer.response.headers.get('etag') ?? '' },
      },
      body: { is_public: true, entity_ids: [], player_ids: [] },
    }),
  );
  const page = await signedIn(browser, world.subject);
  await page.goto(`/entry/?tenant=${world.tenantId}&id=${event.id}`);
  const panel = page.locator('[data-learning]');
  await panel.locator('summary').click();
  await expect(panel.getByText('No learning history is recorded for this Event.')).toBeVisible();
  await panel.getByLabel('Who learned?').selectOption(being.id);
  await panel.getByLabel('Find an entry with Information').fill('Hidden passage');
  await panel.getByRole('button', { name: 'Search entries', exact: true }).click();
  await panel.getByRole('button', { name: 'Hidden passage', exact: true }).click();
  await expect(panel.getByLabel('Information learned').locator('option')).toHaveCount(2);
  await panel.getByLabel('Information learned').selectOption(info.id);
  await panel.getByRole('button', { name: 'Record learning', exact: true }).click();
  await expect(
    panel.getByText('Learning recorded. Audiences are unchanged.', { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText('Mara learned Waterfall entrance (Hidden passage).', { exact: true }),
  ).toBeVisible();
  expect(await audience()).toEqual(before);
  await panel.getByRole('link', { name: 'Learning recorded for Mara', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Recorded learning', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Waterfall entrance', exact: true })).toBeVisible();
  await page.goto(`/entry/?tenant=${world.tenantId}&id=${fact.id}`);
  await page.getByText('Recorded learning', { exact: true }).click();
  await expect(
    page.getByRole('link', { name: 'Prisoner interrogation', exact: true }),
  ).toBeVisible();
  await page.goto(`/entry/?tenant=${world.tenantId}&id=${event.id}`);
  await panel.locator('summary').click();
  // A change after the panel was loaded must not silently overwrite the saved version.
  await ok(
    world.api.PATCH('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { ...path, entity_id: event.id } },
      body: { name: 'Interrogation revised' },
    }),
  );
  await panel.getByRole('button', { name: 'Remove learning record', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Your selection is kept');
  await expect(panel.getByLabel('Who learned?')).toHaveValue('');
  await panel.getByRole('button', { name: 'Refresh saved learning', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText('Saved learning refreshed.');
  await panel.getByRole('button', { name: 'Remove learning record', exact: true }).click();
  await expect(panel.getByText('No learning history is recorded for this Event.')).toBeVisible();
  expect(await audience()).toEqual(before);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('learning-phone.png'), fullPage: true });
  const reader = await signedIn(browser, world.readerSubject);
  const requests: string[] = [];
  reader.on('request', (r) => {
    if (r.url().includes('/event-learning') || r.url().includes('/learning-version'))
      requests.push(r.url());
  });
  await reader.goto(`/entry/?tenant=${world.tenantId}&id=${event.id}`);
  await expect(
    reader.getByRole('heading', { name: 'Interrogation revised', exact: true }),
  ).toBeVisible();
  await expect(reader.locator('[data-learning]')).toHaveCount(0);
  await expect(reader.getByText('Recorded learning', { exact: true })).toHaveCount(0);
  expect(requests).toEqual([]);
  await reader.context().close();
  await page.context().close();
});

test('shared Event order is readable without exposing private relationships or editing controls', async ({
  browser,
}) => {
  const world = await buildWorld();
  const path = { tenant_id: world.tenantId };
  async function create(name: string, publicEntry = true) {
    const e = await ok(
      world.api.POST('/tenants/{tenant_id}/entities', {
        params: { path },
        body: { name, kinds: ['event'], parents: [] },
      }),
    );
    if (publicEntry)
      await ok(
        world.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
          params: {
            path: { ...path, entity_id: e.id },
            header: { 'if-match': `W/"${e.updated_at}"` },
          },
          body: { is_public: true },
        }),
      );
    return e;
  }
  const arrival = await create('Arrival at the harbour');
  const departure = await create('Departure from the harbour');
  const secret = await create('Secret midnight meeting', false);
  async function relate(a: string, b: string, kind: 'order' | 'causes') {
    const p = { ...path, event_id: a };
    const current = await world.api.GET('/tenants/{tenant_id}/events/{event_id}/relationships', {
      params: { path: p },
    });
    await ok(
      world.api.PUT('/tenants/{tenant_id}/events/{event_id}/relationships/{other_event_id}', {
        params: {
          path: { ...p, other_event_id: b },
          header: { 'if-match': current.response.headers.get('etag') ?? '' },
        },
        body: { kind, direction: 'outgoing' },
      }),
    );
  }
  await relate(arrival.id, secret.id, 'causes');
  await relate(secret.id, departure.id, 'causes');
  await relate(arrival.id, departure.id, 'order');
  const reader = await signedIn(browser, world.readerSubject);
  await reader.goto(`/entry/?tenant=${world.tenantId}&id=${arrival.id}`);
  const readPanel = reader.locator('[data-event-order]');
  await readPanel.locator('summary').click();
  await expect(
    readPanel.getByText('No shared relationships are available in your view.'),
  ).toBeVisible();
  await expect(
    readPanel.getByRole('button', { name: 'Add relationship', exact: true }),
  ).toHaveCount(0);
  await expect(reader.locator('[data-participants], [data-learning]')).toHaveCount(0);
  const staff = await signedIn(browser, world.subject);
  await staff.goto(`/entry/?tenant=${world.tenantId}&id=${arrival.id}`);
  const panel = staff.locator('[data-event-order]');
  await panel.locator('summary').click();
  const direct = panel
    .locator('.row')
    .filter({ hasText: 'Happened before' })
    .filter({ hasText: departure.name });
  await expect(direct).toContainText('Private relationship');
  await direct.getByRole('button', { name: 'Share relationship', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText(
    'Relationship shared. Readers still need access to both Events.',
  );
  await reader.reload();
  await readPanel.locator('summary').click();
  await expect(readPanel.getByRole('link', { name: departure.name, exact: true })).toBeVisible();
  await expect(readPanel).not.toContainText(secret.name);
  await readPanel.getByLabel('Find an Event').fill('Departure');
  await readPanel.getByRole('button', { name: 'Search Events', exact: true }).click();
  await readPanel.getByRole('button', { name: departure.name, exact: true }).click();
  await readPanel.getByRole('button', { name: 'Compare Events', exact: true }).click();
  await expect(readPanel).toContainText('Ruled · recorded ordering');
  await expect(readPanel).not.toContainText('Causal · a recorded chain of causes');
  await reader.getByRole('link', { name: 'All Events', exact: true }).click();
  await reader.getByLabel('List order', { exact: true }).selectOption('order');
  await reader.getByRole('button', { name: 'Find Events', exact: true }).click();
  await expect(reader.getByRole('status')).toHaveText('3 Events.');
  await expect(reader.locator('[data-event-list]')).toContainText(
    'Linearized · no visible recorded ordering path',
  );
  await expect(reader.locator('[data-event-list]')).not.toContainText(secret.name);
  await expect(reader.getByText('Participants and causes', { exact: true })).toHaveCount(0);
  await expect(reader.getByText('Causes', { exact: true })).toBeVisible();
  await reader.setViewportSize({ width: 390, height: 844 });
  expect(await reader.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
    true,
  );
  await reader.screenshot({
    path: test.info().outputPath('reader-order-phone.png'),
    fullPage: true,
  });
  await direct.getByRole('button', { name: 'Make relationship private', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText('Relationship is private.');
  await reader.goto(`/entry/?tenant=${world.tenantId}&id=${arrival.id}`);
  await readPanel.locator('summary').click();
  await expect(
    readPanel.getByText('No shared relationships are available in your view.'),
  ).toBeVisible();
  await reader.context().close();
  await staff.context().close();
});

test('players create their own Events and Facts and contribute only their own notes', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.readerSubject);
  await page.goto(`/events/?tenant=${world.tenantId}`);
  await page.getByText('Create an Event', { exact: true }).click();
  await page.getByLabel('Event name', { exact: true }).fill('A player records arrival');
  await page.getByRole('button', { name: 'Create Event', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'A player records arrival', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Learning', { exact: true })).toHaveCount(0);
  await page.getByText('Name, link name and audience', { exact: true }).click();
  await page.getByLabel('Entry name', { exact: true }).fill('Arrival, corrected');
  await page.getByRole('button', { name: 'Save name', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Arrival, corrected', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Add information', exact: true }).click();
  await page.getByLabel('Information title', { exact: true }).fill('My recollection');
  await page.getByRole('textbox', { name: 'Text', exact: true }).fill('We arrived before supper.');
  await page.getByRole('button', { name: 'Save information', exact: true }).click();
  await expect(page.getByText('We arrived before supper.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Edit information', exact: true })).toHaveCount(1);
  await page.goto(`/events/?tenant=${world.tenantId}`);
  await page.getByText('Create an Event', { exact: true }).click();
  await page.getByLabel('Entry kind', { exact: true }).selectOption('fact');
  await page.getByLabel('Event name', { exact: true }).fill('The harbour has a beacon');
  await page.getByRole('button', { name: 'Create Fact', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'The harbour has a beacon', exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.context().close();
});

test('Event creation visibility and participant note audiences remain separate', async ({
  browser,
}) => {
  const world = await buildWorld();
  const page = await signedIn(browser, world.subject);
  await page.goto(`/events/?tenant=${world.tenantId}`);
  await page.getByText('Create an Event', { exact: true }).click();
  await page.getByLabel('Event name', { exact: true }).fill('The participants meet');
  await page.getByLabel('Entry visibility', { exact: true }).selectOption('participants');
  await page.getByRole('button', { name: 'Create Event', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'The participants meet', exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel('Entry visibility', { exact: true })).toHaveValue('participants');
  const id = new URL(page.url()).searchParams.get('id');
  if (!id) throw new Error('Missing Event identity');
  const audience = await ok(
    world.api.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: { tenant_id: world.tenantId, entity_id: id } },
    }),
  );
  expect(audience.shared_with_participants).toBe(true);
  expect(audience.is_public).toBe(false);
  await page.getByRole('button', { name: 'Add information', exact: true }).click();
  await page.getByLabel('Information title', { exact: true }).fill('Shared recollection');
  await page.getByRole('textbox', { name: 'Text', exact: true }).fill('The lantern was blue.');
  await page.getByRole('button', { name: 'Save information', exact: true }).click();
  await expect(page.getByText('The lantern was blue.', { exact: true })).toBeVisible();
  await page.getByText('Who can read this', { exact: true }).click();
  await page.getByLabel('Participants in this Event', { exact: true }).check();
  await page.getByRole('button', { name: 'Save audience', exact: true }).click();
  await expect(page.getByText('Audience saved.', { exact: true })).toBeVisible();
  await page.getByLabel('Entry visibility', { exact: true }).selectOption('restricted');
  await page.getByRole('button', { name: 'Save Event visibility', exact: true }).click();
  await expect(page.getByLabel('Entry visibility', { exact: true })).toHaveValue('restricted');
  await page.context().close();
});

test('Event managers create an ordinary group snapshot including an untracked NPC', async ({
  browser,
}) => {
  const world = await buildWorld();
  const tenant_id = world.tenantId;
  const event = await ok(
    world.api.POST('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id } },
      body: { name: 'The council gathers', kinds: ['event'], parents: [] },
    }),
  );
  const being = await ok(
    world.api.POST('/tenants/{tenant_id}/entities', {
      params: { path: { tenant_id } },
      body: { name: 'Untracked guide', kinds: ['being'], parents: [] },
    }),
  );
  const roster = await world.api.GET('/tenants/{tenant_id}/events/{event_id}/participants', {
    params: { path: { tenant_id, event_id: event.id } },
  });
  await ok(
    world.api.PUT('/tenants/{tenant_id}/events/{event_id}/participants/{being_id}', {
      params: {
        path: { tenant_id, event_id: event.id, being_id: being.id },
        header: { 'if-match': roster.response.headers.get('etag') ?? '' },
      },
    }),
  );
  const page = await signedIn(browser, world.subject);
  await page.goto(`/entry/?tenant=${tenant_id}&id=${event.id}`);
  const participants = page.locator('[data-participants]');
  await participants.getByText('Participating beings', { exact: true }).click();
  await participants.getByText('Create group from event participants', { exact: true }).click();
  await expect(
    participants.getByText('1 participating being(s) will be copied.', { exact: true }),
  ).toBeVisible();
  await expect(
    participants.getByText(/Groups and their members are readable by library participants/),
  ).toBeVisible();
  await participants.getByLabel('Group name', { exact: true }).fill('Council companions');
  await participants.getByRole('button', { name: 'Create group', exact: true }).click();
  const open = participants.getByRole('link', { name: 'Council companions', exact: true });
  await expect(open).toBeVisible();
  const groupId = new URL(
    (await open.getAttribute('href')) ?? '',
    'http://example.test',
  ).searchParams.get('id');
  if (!groupId) throw new Error('Group identity missing');
  const members = await ok(
    world.api.GET('/tenants/{tenant_id}/groups/{group_entity_id}/members', {
      params: { path: { tenant_id, group_entity_id: groupId } },
    }),
  );
  expect(members.map((member) => member.id)).toEqual([being.id]);
  const tracked = await world.api.GET('/tenants/{tenant_id}/characters/{character_id}', {
    params: { path: { tenant_id, character_id: being.id } },
  });
  expect(tracked.response.status).toBe(404);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.context().close();
});
