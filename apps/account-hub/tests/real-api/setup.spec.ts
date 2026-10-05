import { type Browser, expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  AUTHGEAR_URL,
  SITE_URL,
  SUBJECT_COOKIE,
} from '../../../inventory-web/tests/e2e/support/env';
import { libraryCard, newCampaign, newLibrary, newUser, signedInPage } from './support';

const TOKEN_URL = new RegExp(`^${SITE_URL}/join/#[A-Za-z0-9_-]{43}$`);

// What the creator typed into /setup, with names no other test shares.
function names() {
  const id = crypto.randomUUID();
  return { library: `Realms ${id}`, campaign: 'The Open Table', system: 'D&D 5e' };
}

async function fillBasics(page: Page, n: ReturnType<typeof names>) {
  await page.getByLabel('Library name').fill(n.library);
  await page.getByLabel('Campaign name').fill(n.campaign);
  await page.getByLabel('Game system').fill(n.system);
}

// What the creator's account now holds: the library made by name, and its one campaign.
async function whatWasMade(creator: Awaited<ReturnType<typeof newUser>>, libraryName: string) {
  const tenants = await ok(creator.api.GET('/tenants'));
  const library = tenants.items.filter((t) => t.name === libraryName);
  expect(library).toHaveLength(1);
  const [lib] = library;
  if (!lib) throw new Error('library not made');
  const campaigns = await ok(
    creator.api.GET('/tenants/{tenant_id}/campaigns', { params: { path: { tenant_id: lib.id } } }),
  );
  const gms = async (campaignId: string) =>
    ok(
      creator.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/gms', {
        params: { path: { tenant_id: lib.id, campaign_id: campaignId } },
      }),
    );
  const invites = async (campaignId: string) =>
    ok(
      creator.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/invites', {
        params: { path: { tenant_id: lib.id, campaign_id: campaignId } },
      }),
    );
  return { lib, campaigns: campaigns.items, gms, invites };
}

// Someone follows a link as a person who is logged in, and joins through it.
async function joinThrough(
  browser: Browser,
  url: string,
  subject: string,
  button: string,
): Promise<{ page: Page; close: () => Promise<void> }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await context.addCookies([{ name: SUBJECT_COOKIE, value: subject, url: AUTHGEAR_URL }]);
  await page.goto(url);
  await page.getByRole('button', { name: 'Log in to join' }).click();
  await expect(page).toHaveURL(`${SITE_URL}/join/`);
  await page.getByRole('button', { name: button }).click();
  return { page, close: () => context.close() };
}

test('"I do": a library, a campaign, the creator as GM, and a link that works', async ({
  browser,
}) => {
  const creator = await newUser('creator', ['tenant_creator']);
  const n = names();
  const { page, context } = await signedInPage(browser, creator.subject);
  await page.goto('/setup');
  await expect(page.getByRole('heading', { name: 'Set up a table' })).toBeVisible();
  await fillBasics(page, n);
  await page.getByRole('button', { name: 'Set up' }).click();

  await expect(page.getByRole('heading', { name: 'Your table is ready' })).toBeVisible();
  await expect(page.locator('#setup-container')).toContainText(`${n.campaign} is in ${n.library}.`);
  await expect(page.locator('#setup-container')).toContainText("You're its GM.");
  const link = page.getByLabel('Link for your players');
  await expect(link).toHaveValue(TOKEN_URL);
  await expect(page.locator('.setup-link')).toContainText("won't be shown again");
  // No GM link when the creator runs it.
  await expect(page.getByLabel('GM invite link')).toHaveCount(0);

  // What the API holds: a library (a play one, owned by the creator), its campaign with a
  // slug made from the name, the creator as its GM, and one player link with no use limit.
  const made = await whatWasMade(creator, n.library);
  expect(made.lib.kind).toBe('play');
  expect(made.lib.role).toBe('owner');
  expect(made.campaigns.map((c) => [c.name, c.slug, c.game_system])).toEqual([
    [n.campaign, 'the-open-table', n.system],
  ]);
  const campaignId = made.campaigns[0]?.id as string;
  expect((await made.gms(campaignId)).map((g) => g.user_id)).toEqual([creator.me.id]);
  const invites = (await made.invites(campaignId)).items;
  expect(invites.map((i) => [i.role, i.max_uses])).toEqual([['player', null]]);

  // The link works: a visitor joins as a player through it.
  const url = await link.inputValue();
  const visitor = await newUser('visitor');
  const joined = await joinThrough(browser, url, visitor.subject, 'Join');
  await expect(joined.page.locator('#invite-status')).toHaveText(
    `You're in. ${n.campaign} lists you as a player.`,
  );
  await joined.close();

  // "Done" takes the link off the page.
  await page.locator('.setup-link').getByRole('button', { name: 'Done' }).click();
  await expect(page.getByLabel('Link for your players')).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Your campaigns' })).toHaveAttribute(
    'href',
    '/campaigns',
  );
  await context.close();
});

test('"someone I can find": the person found is made GM now, and the creator is not', async ({
  browser,
}) => {
  const creator = await newUser('creator', ['tenant_creator']);
  const friend = await newUser('friend');
  const nickname = `friend-${crypto.randomUUID().slice(0, 8)}`;
  await ok(friend.api.PATCH('/me', { body: { nickname } }));
  const n = names();
  const { page, context } = await signedInPage(browser, creator.subject);
  await page.goto('/setup');
  await fillBasics(page, n);
  await page.getByLabel('Someone I can find').check();

  // Not looked up yet: said, and nothing is made.
  await page.getByRole('button', { name: 'Set up' }).click();
  await expect(page.locator('#setup-container')).toContainText('Look the person up first');
  expect((await ok(creator.api.GET('/tenants'))).items.map((t) => t.name)).not.toContain(n.library);

  await page.getByLabel('Nickname', { exact: true }).check();
  await page.getByPlaceholder('Email or nickname').fill(nickname);
  await page.getByRole('button', { name: 'Look up' }).click();
  await expect(page.locator('#setup-container')).toContainText(`Found: ${nickname}`);
  await page.getByRole('button', { name: 'Set up' }).click();

  await expect(page.getByRole('heading', { name: 'Your table is ready' })).toBeVisible();
  await expect(page.locator('#setup-container')).toContainText(`${nickname} is its GM.`);
  const made = await whatWasMade(creator, n.library);
  const campaignId = made.campaigns[0]?.id as string;
  expect((await made.gms(campaignId)).map((g) => g.user_id)).toEqual([friend.me.id]);
  await context.close();
});

test('"someone I\'ll send a link to": a single-use GM link that makes a GM and nothing else', async ({
  browser,
}) => {
  const creator = await newUser('creator', ['tenant_creator']);
  const n = names();
  const { page, context } = await signedInPage(browser, creator.subject);
  await page.goto('/setup');
  await fillBasics(page, n);
  await page.getByLabel("Someone I'll send a link to").check();
  await expect(page.getByLabel('GM link works for')).toBeVisible();
  await page.getByRole('button', { name: 'Set up' }).click();

  await expect(page.getByRole('heading', { name: 'Your table is ready' })).toBeVisible();
  await expect(page.locator('#setup-container')).toContainText(
    'Send the GM link to the person who should run it.',
  );
  const gmLink = page.getByLabel('GM invite link');
  await expect(gmLink).toHaveValue(TOKEN_URL);
  await expect(page.getByLabel('Link for your players')).toHaveValue(TOKEN_URL);
  await expect(page.locator('.setup-link').first()).toContainText('works once');

  const made = await whatWasMade(creator, n.library);
  const campaignId = made.campaigns[0]?.id as string;
  // No GM yet: the creator owns the library, and has not made themselves one.
  expect(await made.gms(campaignId)).toEqual([]);
  const invites = (await made.invites(campaignId)).items;
  expect(invites.map((i) => [i.role, i.max_uses]).sort()).toEqual([
    ['gm', 1],
    ['player', null],
  ]);

  // Someone with no account of their own yet follows it: the page says what it offers, and
  // joining makes them a GM, never a player and never a library member.
  const gmUrl = await gmLink.inputValue();
  const newcomer = await newUser('gm-newcomer');
  const context2 = await browser.newContext();
  const joinPage = await context2.newPage();
  await joinPage.goto(gmUrl);
  await expect(joinPage.locator('#invite-offer')).toHaveText(
    "You've been invited to run this campaign as a GM.",
  );
  await context2.addCookies([{ name: SUBJECT_COOKIE, value: newcomer.subject, url: AUTHGEAR_URL }]);
  await joinPage.getByRole('button', { name: 'Log in to join' }).click();
  await expect(joinPage).toHaveURL(`${SITE_URL}/join/`);
  await joinPage.getByRole('button', { name: 'Join as a GM' }).click();
  await expect(joinPage.locator('#invite-status')).toHaveText(
    `You're in. ${n.campaign} lists you as a GM.`,
  );
  expect((await made.gms(campaignId)).map((g) => g.user_id)).toEqual([newcomer.me.id]);
  const theirs = await ok(newcomer.api.GET('/me'));
  expect(theirs.players).toHaveLength(0);
  expect(theirs.memberships).toHaveLength(0);
  expect(theirs.campaign_gm_grants.map((c) => c.id)).toEqual([campaignId]);

  // It works once: the next person is told it doesn't work, as for any dead link.
  const second = await newUser('gm-second');
  const context3 = await browser.newContext();
  const page3 = await context3.newPage();
  await context3.addCookies([{ name: SUBJECT_COOKIE, value: second.subject, url: AUTHGEAR_URL }]);
  await page3.goto(gmUrl);
  await expect(page3.locator('#dead-link')).toHaveText(
    "This link doesn't work any more. Ask whoever sent it for a new one.",
  );
  expect((await made.gms(campaignId)).map((g) => g.user_id)).toEqual([newcomer.me.id]);
  await context2.close();
  await context3.close();
  await context.close();
});

test('a step that fails stops there, says why, and goes on from it without making anything twice', async ({
  browser,
}) => {
  const creator = await newUser('creator', ['tenant_creator']);
  const n = names();
  const { page, context } = await signedInPage(browser, creator.subject);
  // The first campaign the page tries to make is refused by "the server".
  let refused = 0;
  await page.route('**/tenants/*/campaigns', async (route) => {
    if (route.request().method() === 'POST' && refused === 0) {
      refused += 1;
      await route.fulfill({
        status: 500,
        contentType: 'application/problem+json',
        body: JSON.stringify({
          type: 'about:blank',
          title: 'Internal Server Error',
          status: 500,
          detail: 'The campaign could not be made just now.',
        }),
      });
      return;
    }
    await route.continue();
  });
  await page.goto('/setup');
  await fillBasics(page, n);
  await page.getByRole('button', { name: 'Set up' }).click();

  // The library is made and said so; the campaign is where it stopped, and why.
  await expect(page.locator('.setup-steps')).toContainText('✓ Library made');
  await expect(page.locator('.setup-steps')).toContainText('✗ Making the campaign');
  await expect(page.getByRole('alert')).toContainText('The campaign could not be made just now.');
  await expect(page.getByRole('alert')).toContainText('What is already made is kept');
  await expect(page.getByRole('alert')).not.toContainText('{');
  expect(
    (await ok(creator.api.GET('/tenants'))).items.filter((t) => t.name === n.library),
  ).toHaveLength(1);

  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'Your table is ready' })).toBeVisible();

  // Still one library: the retry went on from the campaign.
  const made = await whatWasMade(creator, n.library);
  expect(made.campaigns).toHaveLength(1);
  const campaignId = made.campaigns[0]?.id as string;
  expect((await made.gms(campaignId)).map((g) => g.user_id)).toEqual([creator.me.id]);
  expect((await made.invites(campaignId)).items).toHaveLength(1);
  await context.close();
});

test('only an account the API says may create is offered setup, and the links to it follow', async ({
  browser,
}) => {
  const plain = await newUser('plain');
  const refused = await signedInPage(browser, plain.subject);
  await refused.page.goto('/setup');
  await expect(refused.page.locator('#loading')).toBeHidden();
  await expect(refused.page.locator('#setup-unavailable')).toBeVisible();
  await expect(refused.page.locator('#setup-unavailable')).toContainText(
    "isn't open to your account yet",
  );
  await expect(refused.page.locator('#setup form')).toHaveCount(0);
  await refused.page.goto('/');
  await expect(refused.page.locator('#account-signed-in')).toBeVisible();
  await expect(refused.page.locator('#setup-link')).toBeHidden();
  await refused.page.goto('/campaigns');
  await expect(refused.page.locator('#empty-state')).toBeVisible();
  await expect(refused.page.locator('#setup-link')).toBeHidden();
  await refused.context.close();

  const maker = await newUser('maker', ['tenant_creator']);
  const { page, context } = await signedInPage(browser, maker.subject);
  await page.goto('/');
  await expect(page.getByRole('link', { name: 'Set up a table' })).toBeVisible();
  // Nothing yet, on either page: both point at it.
  for (const path of ['/campaigns', '/tenants']) {
    await page.goto(path);
    await expect(page.locator('#empty-state')).toBeVisible();
    await expect(
      page.locator('#empty-state').getByRole('link', { name: 'Set up a table' }),
    ).toHaveAttribute('href', '/setup');
  }
  await context.close();
});

test('a campaign manager hands over a GM seat from the invite panel, one use, labelled as a GM link', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Zorro');
  const { page, context } = await signedInPage(browser, owner.subject);
  await page.goto('/tenants');
  const panel = libraryCard(page, library.name)
    .locator('.panel')
    .filter({ hasText: 'Invite links:' });

  await panel.getByRole('button', { name: 'Invite a GM' }).click();
  const link = panel.getByLabel('GM invite link');
  await expect(link).toHaveValue(TOKEN_URL);
  await expect(panel).toContainText('works once');
  await expect(panel).toContainText('becomes a GM');
  await expect(panel.locator('li').filter({ hasText: 'GM link' })).toContainText('Used 0 of 1');

  const [made] = (
    await ok(
      owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/invites', {
        params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
      }),
    )
  ).items;
  expect(made?.role).toBe('gm');
  expect(made?.max_uses).toBe(1);
  // At most a week, with the slack the presets keep under it.
  const hours = (new Date(made?.expires_at ?? 0).getTime() - Date.now()) / 3_600_000;
  expect(hours).toBeGreaterThan(24);
  expect(hours).toBeLessThan(7 * 24);
  await context.close();
});
