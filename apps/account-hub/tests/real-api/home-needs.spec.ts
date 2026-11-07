import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addItem,
  invite,
  newCampaign,
  newLibrary,
  newRepository,
  newUser,
  publish,
  signedInPage,
} from './support';

// What needs a person, on Home (AH6): tasks computed from what they run, never news.

const DAY = 24 * 60 * 60 * 1000;

test('Home lists an update, a link about to end, a new player and a draft, each with where to go', async ({
  browser,
}) => {
  test.slow();

  const owner = await newUser('owner', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const library = await newLibrary(owner.api, `Table ${tag}`);
  const campaign = await newCampaign(owner.api, library.id, `Harbour ${tag}`);
  const repository = await newRepository(owner.api, `Core ${tag}`);

  // Copied, then released again: an update is announced.
  await addItem(owner.api, repository.id, 'Anvil');
  await publish(owner.api, repository.id);
  await invite(owner.api, repository.id, library.id);
  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: library.id, repository_id: repository.id } },
      body: {},
    }),
  );
  await addItem(owner.api, repository.id, 'Hammer');
  await publish(owner.api, repository.id);

  // A draft of their own.
  await newRepository(owner.api, `Draft ${tag}`);

  // A player link that ends in two days and a half, and one person who used it.
  const link = await ok(
    owner.api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/invites', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
      body: {
        role: 'player',
        expires_at: new Date(Date.now() + 2.5 * DAY).toISOString(),
        max_uses: 10,
      },
    }),
  );
  const player = await newUser('player');

  await ok(player.api.POST('/invites/{token}/redeem', { params: { path: { token: link.token } } }));

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto('/');

  const needs = page.locator('[data-needs]');
  const task = (text: string) => needs.locator('[data-needs-list] > li').filter({ hasText: text });

  await expect(task(`Core ${tag} has an update announced for Table ${tag}.`)).toBeVisible();
  await expect(
    task(`An invite link for Harbour ${tag} ends in 2 days (used 1 of 10 times).`),
  ).toBeVisible();
  await expect(task(`A new player joined Harbour ${tag}.`)).toBeVisible();
  await expect(task(`Draft ${tag} is still a draft.`)).toBeVisible();

  // Each leads to where the work is, and they come in the order of the design.
  await expect(
    task('has an update announced').getByRole('link', { name: 'Review updates' }),
  ).toHaveAttribute('href', /updates=1/);
  await expect(
    task('An invite link').getByRole('link', { name: 'Make a new link' }),
  ).toHaveAttribute('href', new RegExp(`tenant=${library.slug}`));
  await expect(needs.locator('[data-needs-list] > li').first()).toContainText('update announced');

  // Notifications are news, and stay out of it.
  await expect(needs).not.toContainText('joined Harbour as');
  await context.close();
});

test('a person who runs nothing is caught up, with nothing in Needs you', async ({ browser }) => {
  const person = await newUser('quiet', ['tenant_creator']);

  await newLibrary(person.api);

  const { page, context } = await signedInPage(browser, person.subject);

  await page.goto('/');
  await expect(page.locator('[data-needs]')).toContainText('You’re all caught up');
  await expect(page.locator('[data-needs-list] > li')).toHaveCount(0);
  await context.close();
});
