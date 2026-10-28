import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { type Browser, expect, type Page, test } from '@playwright/test';
import { apiAs, ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';

async function signedIn(browser: Browser, subject: string, theme?: 'light' | 'dark') {
  const token = await refreshTokenFor(subject);
  const localStorage = [{ name: REFRESH_TOKEN_KEY, value: token }];
  if (theme) localStorage.push({ name: 'lorenzo:maps:theme', value: theme });
  const context = await browser.newContext({
    storageState: { cookies: [], origins: [{ origin: SITE_URL, localStorage }] },
  });
  return context.newPage();
}

const DEFINITION = {
  format: 'lorenzo.calendar/1',
  segments: [
    { key: 'first', name: 'First', days: 27 },
    { key: 'festival', name: 'Festival', days: 2, kind: 'festival', in_week: false },
  ],
};

/** A library with a GM and a player. */
async function world() {
  const subject = `maps-gm-${randomUUID()}`;
  const gm = await apiAs(subject, ['tenant_creator']);
  const me = await ok(gm.GET('/me'));
  const tenant = await ok(gm.POST('/tenants', { body: { name: `Maps library ${randomUUID()}` } }));
  const path = { tenant_id: tenant.id };
  const campaign = await ok(
    gm.POST('/tenants/{tenant_id}/campaigns', {
      params: { path },
      body: {
        name: 'Harbour campaign',
        game_system: 'Homebrew',
        slug: `harbour-${randomUUID()}`,
        description: '',
        secret: false,
      },
    }),
  );
  await ok(
    gm.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { ...path, campaign_id: campaign.id, user_id: me.id } },
    }),
  );
  const playerSubject = `maps-player-${randomUUID()}`;
  const player = await apiAs(playerSubject);
  const playerMe = await ok(player.GET('/me'));
  await ok(
    gm.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { ...path, campaign_id: campaign.id } },
      body: { user_id: playerMe.id },
    }),
  );
  return { subject, gm, tenant, playerSubject, path };
}

type World = Awaited<ReturnType<typeof world>>;

async function openUp(w: World, id: string) {
  const at = { params: { path: { ...w.path, entity_id: id } } };
  const { data, response } = await w.gm.GET(
    '/tenants/{tenant_id}/entities/{entity_id}/audience',
    at,
  );
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: at.params.path, header: { 'if-match': response.headers.get('etag') } },
      body: { ...(data as object), is_public: true } as never,
    }),
  );
}

async function calendarWith(
  w: World,
  ...dates: { year: number; segment?: string; day?: number }[]
) {
  const made = await ok(
    w.gm.POST('/tenants/{tenant_id}/calendars', {
      params: { path: w.path },
      body: { name: 'Calendar', definition: DEFINITION } as never,
    }),
  );
  const calendar = (made as { entity_id: string }).entity_id;
  await openUp(w, calendar);
  const ids: string[] = [];
  for (const date of dates) {
    const period = await ok(
      w.gm.POST('/tenants/{tenant_id}/calendars/{calendar_id}/periods', {
        params: { path: { ...w.path, calendar_id: calendar } },
        body: date as never,
      }),
    );
    ids.push((period as { entity_id: string }).entity_id);
  }
  return { calendar, ids };
}

async function placeTiedTo(w: World, name: string, periods: string[], parent?: string) {
  const made = await ok(
    w.gm.POST('/tenants/{tenant_id}/locations', {
      params: { path: w.path },
      body: { name, is_public: true, ...(parent ? { parent_id: parent } : {}) },
    }),
  );
  if (periods.length) {
    const at = { params: { path: { ...w.path, entity_id: made.id } } };
    const { response } = await w.gm.GET('/tenants/{tenant_id}/entities/{entity_id}', at);
    await ok(
      w.gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/dates', {
        params: { path: at.params.path, header: { 'if-match': response.headers.get('etag') } },
        body: { period_ids: periods },
      }),
    );
  }
  return made;
}

async function seeded(w: World) {
  const { ids } = await calendarWith(
    w,
    { year: 3286 },
    { year: 3286, segment: 'first' },
    { year: 3287 },
  );
  for (const id of ids) await openUp(w, id);
  const [year, month, nextYear] = ids as [string, string, string];
  const town = await placeTiedTo(w, 'Town', [year]);
  await placeTiedTo(w, 'Inn', [month], town.id);
  await placeTiedTo(w, 'Harbour', [nextYear]);
  await placeTiedTo(w, 'Ruin', []);
}

const here = (tenant: string) => `/locations/?tenant=${tenant}`;
const roots = (page: Page) => page.locator('#maps-locations ul.place-tree > li');

async function chooseDay(page: Page, year: number, day: number) {
  const picker = page.locator('.period-picker');
  const input = picker.getByRole('spinbutton', { name: 'Year' });
  await input.fill(String(year));
  await input.press('Enter');
  await picker.getByRole('button', { name: `${day} First ${year}`, exact: true }).click();
}

test('the Locations page can be looked at through a date, and the tree comes back', async ({
  browser,
}) => {
  const w = await world();
  await placeTiedTo(w, 'Ruin', []);
  const page = await signedIn(browser, w.subject);
  try {
    await page.goto(here(w.tenant.id));
    await expect(roots(page)).toHaveCount(1);
    await expect(page.getByRole('group', { name: 'Tied to a date' })).toHaveCount(0);

    await seeded(w);
    await page.reload();
    await expect(page.getByRole('group', { name: 'Tied to a date' })).toBeVisible();
    // It opens empty: the tree of roots, with what is inside them folded away.
    await expect(roots(page)).toHaveCount(4);
    await expect(page.locator('.chip')).toHaveCount(0);
    await expect(page.getByText('With a date chosen')).toHaveCount(0);

    await chooseDay(page, 3286, 16);
    await expect(
      page.getByText('With a date chosen the Locations are listed by name'),
    ).toBeVisible();
    await expect(page.getByText('Tied to this date')).toHaveCount(2);
    await expect(page.getByText('Not tied to a date')).toHaveCount(2);
    await expect(page.getByText('Tied to other dates')).toHaveCount(1);
    // The inn, which is inside the town, is now a row of its own; tied first, then not tied, then
    // tied to other dates, by name within each.
    const names = (await roots(page).locator('a').allTextContents()).map((text) => text.trim());
    expect(names).toEqual(['Inn', 'Town', 'Ruin', 'Ruin', 'Harbour']);
    await expect(page.locator('.map-other')).toHaveCount(1);

    await page.getByLabel('Leave out Locations tied only to other dates').check();
    await expect(roots(page)).toHaveCount(4);
    await expect(page.getByText('4 Locations left.')).toBeVisible();
    await expect(page.getByText('Tied to other dates')).toHaveCount(0);

    // A search narrows the list and keeps the date.
    await page.getByLabel('Find a Location').fill('inn');
    await expect(roots(page)).toHaveCount(1);
    await page.getByLabel('Find a Location').fill('');

    await page.getByRole('button', { name: 'Clear the date' }).click();
    await expect(page.getByText('With a date chosen')).toHaveCount(0);
    await expect(page.locator('.chip')).toHaveCount(0);
    await expect(roots(page)).toHaveCount(4);
    await expect(page.getByRole('button', { name: /Show what is inside Town/ })).toBeVisible();
  } finally {
    await page.context().close();
  }
});

test('a player reads a date they cannot see as not tied', async ({ browser }) => {
  const w = await world();
  const { ids } = await calendarWith(w, { year: 3286 }, { year: 3290 });
  await openUp(w, ids[0] as string);
  await placeTiedTo(w, 'Open tie', [ids[0] as string]);
  await placeTiedTo(w, 'Private tie', [ids[1] as string]);
  const gm = await signedIn(browser, w.subject);
  const player = await signedIn(browser, w.playerSubject);
  try {
    for (const page of [gm, player]) {
      await page.goto(here(w.tenant.id));
      await expect(page.getByRole('group', { name: 'Tied to a date' })).toBeVisible();
      const input = page.locator('.period-picker').getByRole('spinbutton', { name: 'Year' });
      await input.fill('3286');
      await input.press('Enter');
      await page.getByRole('button', { name: 'Choose this year' }).click();
    }
    await expect(gm.getByText('Tied to this date')).toHaveCount(1);
    await expect(gm.getByText('Tied to other dates')).toHaveCount(1);
    await expect(player.getByText('Tied to this date')).toHaveCount(1);
    await expect(player.getByText('Not tied to a date')).toHaveCount(1);
    await expect(player.getByText('Tied to other dates')).toHaveCount(0);
  } finally {
    await gm.context().close();
    await player.context().close();
  }
});

for (const theme of ['light', 'dark'] as const) {
  test(`the date lens on Locations has no accessibility errors in ${theme}`, async ({
    browser,
  }) => {
    const w = await world();
    await seeded(w);
    const page = await signedIn(browser, w.subject, theme);
    try {
      await page.goto(here(w.tenant.id));
      await expect(page.getByRole('group', { name: 'Tied to a date' })).toBeVisible();
      const before = await new AxeBuilder({ page }).analyze();
      expect(before.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
      await chooseDay(page, 3286, 16);
      await expect(page.getByText('Tied to other dates')).toHaveCount(1);
      const after = await new AxeBuilder({ page }).analyze();
      expect(after.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    } finally {
      await page.context().close();
    }
  });
}
