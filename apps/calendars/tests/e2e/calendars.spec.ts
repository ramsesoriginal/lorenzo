import { type Browser, expect, type Page, test } from '@playwright/test';
import { ok, refreshTokenFor } from './support/api.ts';
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
  await expect(page.getByRole('button', { name: 'Add information', exact: true })).toHaveCount(0);
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
  await expect(page.getByRole('heading', { name: 'Calendars for your worlds' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeVisible();
  await expect(page.locator('.brand-mark--light')).toBeVisible();
  expect(
    await page
      .locator('.brand-mark--light')
      .evaluate((node) => (node as HTMLImageElement).naturalWidth),
  ).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.brand-mark--dark')).toBeVisible();
  expect(
    await page
      .locator('.brand-mark--dark')
      .evaluate((node) => (node as HTMLImageElement).naturalWidth),
  ).toBeGreaterThan(0);
  await expect(page.getByRole('button', { name: 'Light theme', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('welcome-dark-phone.png'), fullPage: true });
  await page.getByRole('button', { name: 'Light theme', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.setViewportSize({ width: 1280, height: 900 });
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
  // The reader can read this Event, but gets no structured-order surface or requests.
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
  await expect(reader.locator('[data-event-order]')).toHaveCount(0);
  expect(graphRequests).toEqual([]);
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
  await expect(reader.getByText('Create an Event', { exact: true })).toHaveCount(0);
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
