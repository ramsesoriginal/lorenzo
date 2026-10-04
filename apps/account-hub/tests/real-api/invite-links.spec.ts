import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  API_URL,
  AUTHGEAR_URL,
  SITE_URL,
  SUBJECT_COOKIE,
} from '../../../inventory-web/tests/e2e/support/env';
import { libraryCard, newCampaign, newLibrary, newUser, signedInPage } from './support';

async function setup() {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Zorro');
  return { owner, library, campaign };
}

const inviteIn = (
  owner: Awaited<ReturnType<typeof setup>>['owner'],
  tenantId: string,
  campaignId: string,
) =>
  ok(
    owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/invites', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
    }),
  );

test('a manager makes a link, sees it once, lists it without a token, and revokes it', async ({
  browser,
}) => {
  const { owner, library, campaign } = await setup();
  const session = await signedInPage(browser, owner.subject, {
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  const { page } = session;
  await page.goto('/tenants');
  const panel = libraryCard(page, library.name)
    .locator('.panel')
    .filter({ hasText: 'Invite links:' });

  // A limit that isn't a number is said, not sent.
  await panel.getByPlaceholder('No limit').fill('lots');
  await panel.getByRole('button', { name: 'Create link' }).click();
  await expect(panel).toContainText('Use a whole number of 1 or more');
  expect((await inviteIn(owner, library.id, campaign.id)).items).toEqual([]);

  await panel.getByPlaceholder('No limit').fill('2');
  await panel.getByRole('button', { name: 'Create link' }).click();
  const link = panel.getByLabel('Invite link');
  await expect(link).toBeVisible();
  const url = await link.inputValue();
  expect(url).toMatch(new RegExp(`^${SITE_URL}/join/#[A-Za-z0-9_-]{43}$`));
  await expect(panel).toContainText("won't be shown again");
  await panel.getByRole('button', { name: 'Copy' }).click();
  await expect(panel).toContainText('Copied.');
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(url);

  // What the API holds: one link, a limit of two, expiring about a week out.
  const [made] = (await inviteIn(owner, library.id, campaign.id)).items;
  expect(made?.max_uses).toBe(2);
  const inAWeek = Date.now() + 7 * 24 * 60 * 60 * 1000;
  expect(Math.abs(new Date(made?.expires_at ?? 0).getTime() - inAWeek)).toBeLessThan(60_000);

  // The list shows it with its counts and never the token.
  const token = url.split('#')[1] ?? '';
  const row = panel.locator('li').first();
  await expect(row).toContainText('Active');
  await expect(row).toContainText('Used 0 of 2');
  await expect(panel.locator('li')).not.toContainText(token);

  // Done removes the link from the page; so does coming back to it.
  await panel.getByRole('button', { name: 'Done' }).click();
  await expect(panel.getByLabel('Invite link')).toHaveCount(0);
  await page.reload();
  const again = libraryCard(page, library.name)
    .locator('.panel')
    .filter({ hasText: 'Invite links:' });
  await expect(again.locator('li').first()).toContainText('Active');
  expect(await page.content()).not.toContain(token);

  await again.getByRole('button', { name: 'Revoke' }).click();
  await expect(again.locator('li').first()).toContainText('Revoked');
  await expect(again.getByRole('button', { name: 'Revoke' })).toHaveCount(0);
  expect(session.confirmations.at(-1)).toContain('Revoke this link?');
  expect((await inviteIn(owner, library.id, campaign.id)).items[0]?.revoked_at).not.toBeNull();
  await session.context.close();
});

test('a visitor follows a link, logs in, joins, and every dead link reads the same', async ({
  browser,
}) => {
  const { owner, library, campaign } = await setup();
  const created = await ok(
    owner.api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/invites', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
      body: { expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString() },
    }),
  );
  const visitor = await newUser('visitor');
  const context = await browser.newContext();
  const page = await context.newPage();
  const referers: string[] = [];
  page.on('request', (request) => {
    if (request.url().startsWith(API_URL) && request.headers().referer) {
      referers.push(`${request.method()} ${request.url().replace(created.token, '<token>')}`);
    }
  });

  // Not logged in: the campaign is previewed, and the token is out of the address bar.
  await page.goto(`/join/#${created.token}`);
  await expect(page.locator('#invite-campaign')).toHaveText('Zorro');
  expect(page.url()).toBe(`${SITE_URL}/join/`);
  expect(await page.evaluate(() => sessionStorage.getItem('lorenzo.invite'))).toBe(created.token);

  // The token survives the login round trip, and Join is what redeems it.
  await context.addCookies([{ name: SUBJECT_COOKIE, value: visitor.subject, url: AUTHGEAR_URL }]);
  await page.getByRole('button', { name: 'Log in to join' }).click();
  await expect(page).toHaveURL(`${SITE_URL}/join/`);
  await expect(page.locator('#invite-campaign')).toHaveText('Zorro');
  await page.getByRole('button', { name: 'Join' }).click();
  await expect(page.locator('#invite-status')).toHaveText(
    "You're in. Zorro lists you as a player.",
  );
  expect(await page.evaluate(() => sessionStorage.getItem('lorenzo.invite'))).toBeNull();
  const players = await ok(
    owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
    }),
  );
  expect(players.items.map((p) => p.user_id)).toEqual([visitor.me.id]);

  // Opening it again is not a second seat, and uses nothing.
  await page.goto(`/join/#${created.token}`);
  await page.getByRole('button', { name: 'Join' }).click();
  await expect(page.locator('#invite-status')).toHaveText("You're already a player in Zorro.");
  expect((await inviteIn(owner, library.id, campaign.id)).items[0]?.use_count).toBe(1);

  // Nothing the page asked of the API carried a Referer.
  expect(referers).toEqual([]);

  // Revoked, and never issued: the same sentence, and no way to tell which.
  await ok(
    owner.api.DELETE('/tenants/{tenant_id}/campaigns/{campaign_id}/invites/{invite_id}', {
      params: {
        path: { tenant_id: library.id, campaign_id: campaign.id, invite_id: created.id },
      },
    }),
  );
  const dead = "This link doesn't work any more. Ask whoever sent it for a new one.";
  await page.goto(`/join/#${created.token}`);
  await expect(page.locator('#dead-link')).toHaveText(dead);
  await page.goto(`/join/#${'x'.repeat(43)}`);
  await expect(page.locator('#dead-link')).toHaveText(dead);
  await expect(page.locator('#invite')).toBeHidden();
  await context.close();
});

test('the built site sends no referrer from /join/', async ({ request }) => {
  const headers = await request.get(`${SITE_URL}/_headers`);
  expect(headers.ok()).toBe(true);
  expect(await headers.text()).toContain('Referrer-Policy: no-referrer');
});
