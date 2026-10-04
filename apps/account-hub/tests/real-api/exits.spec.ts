import { expect, test } from '@playwright/test';
import { apiAs, ok } from '../../../inventory-web/tests/e2e/support/api';
import { libraryCard as card, newLibrary, newUser, signedInPage } from './support';

test('an organizer leaves a library; the only owner is told to hand it over first', async ({
  browser,
}) => {
  const ownerSubject = `hub-owner-${crypto.randomUUID()}`;
  const owner = await apiAs(ownerSubject, ['tenant_creator']);
  await ok(owner.GET('/me'));
  const library = await newLibrary(owner);
  const orga = await newUser('orga');
  await ok(
    owner.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: library.id } },
      body: { user_id: orga.me.id, role: 'orga' },
    }),
  );

  // The organizer has no owner-only controls, and can still leave.
  const leaver = await signedInPage(browser, orga.subject);
  await leaver.page.goto('/tenants');
  await expect(card(leaver.page, library.name)).toBeVisible();
  await expect(leaver.page.getByRole('button', { name: 'Remove', exact: true })).toHaveCount(0);
  await card(leaver.page, library.name).getByRole('button', { name: 'Leave this library' }).click();
  await expect(card(leaver.page, library.name)).toHaveCount(0);
  expect(leaver.confirmations[0]).toContain(`Leave "${library.name}"?`);
  const remaining = await ok(orga.api.GET('/tenants'));
  expect(remaining.items.map((t) => t.id)).not.toContain(library.id);
  await leaver.context.close();

  // The owner is now the only one: leaving is refused, in words, naming the library.
  const stayer = await signedInPage(browser, ownerSubject);
  await stayer.page.goto('/tenants');
  const row = card(stayer.page, library.name);
  await row.getByRole('button', { name: 'Leave this library' }).click();
  await expect(row).toContainText(`You're the only owner of "${library.name}"`);
  await expect(row).toContainText('Make someone else an owner first');
  await expect(row).not.toContainText('{');
  const still = await ok(owner.GET('/tenants'));
  expect(still.items.map((t) => t.id)).toContain(library.id);
  await stayer.context.close();
});

test('a campaign GM with no library membership steps down', async ({ browser }) => {
  const owner = await apiAs(`hub-owner-${crypto.randomUUID()}`, ['tenant_creator']);
  await ok(owner.GET('/me'));
  const library = await newLibrary(owner);
  const campaign = await ok(
    owner.POST('/tenants/{tenant_id}/campaigns', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Zorro', slug: 'zorro', description: '', game_system: 'test', secret: false },
    }),
  );
  const gm = await newUser('gm');
  await ok(
    owner.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id, user_id: gm.me.id } },
    }),
  );

  const session = await signedInPage(browser, gm.subject);
  await session.page.goto('/tenants');
  const row = card(session.page, library.name);
  // A GM with no membership has nothing to leave, only the GM seat to give up.
  await expect(row.getByRole('button', { name: 'Leave this library' })).toHaveCount(0);
  await row.getByRole('button', { name: 'Step down as GM' }).click();
  await expect(card(session.page, library.name)).toHaveCount(0);
  expect(session.confirmations[0]).toContain('Step down as GM of "Zorro"?');
  const gms = await ok(
    owner.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/gms', {
      params: { path: { tenant_id: library.id, campaign_id: campaign.id } },
    }),
  );
  expect(gms.map((g) => g.user_id)).not.toContain(gm.me.id);
  await session.context.close();
});

test('deleting an account removes it everywhere, and a new login is a fresh one', async ({
  browser,
}) => {
  const owner = await apiAs(`hub-owner-${crypto.randomUUID()}`, ['tenant_creator']);
  await ok(owner.GET('/me'));
  const library = await newLibrary(owner);
  const leaver = await newUser('leaver');
  await ok(
    owner.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: library.id } },
      body: { user_id: leaver.me.id, role: 'orga' },
    }),
  );

  const session = await signedInPage(browser, leaver.subject);
  await session.page.goto('/profile');
  const zone = session.page.locator('#danger-zone');
  await expect(zone).toBeVisible();
  await zone.getByRole('button', { name: 'Delete my account' }).click();
  await expect(session.page.locator('#login-button')).toBeVisible();
  const text = session.confirmations[0] ?? '';
  expect(text).toContain('does not delete your Authgear login');
  expect(text).toContain('fresh, empty Lorenzo account');

  // The same Authgear login gets a new, empty Lorenzo account.
  const again = await ok(leaver.api.GET('/me'));
  expect(again.id).not.toBe(leaver.me.id);
  expect(again.memberships).toEqual([]);
  const roster = await ok(
    owner.GET('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: library.id } },
    }),
  );
  expect(roster.items.map((entry) => entry.user_id)).not.toContain(leaver.me.id);
  await session.context.close();
});

test('the only owner of a library cannot delete their account, and is told which', async ({
  browser,
}) => {
  const subject = `hub-owner-${crypto.randomUUID()}`;
  const owner = await apiAs(subject, ['tenant_creator']);
  const me = await ok(owner.GET('/me'));
  const library = await newLibrary(owner);

  const session = await signedInPage(browser, subject);
  await session.page.goto('/profile');
  await session.page
    .locator('#danger-zone')
    .getByRole('button', { name: 'Delete my account' })
    .click();
  await expect(session.page.locator('#danger-zone')).toContainText(
    `You're the only owner of "${library.name}", so your account can't be deleted yet.`,
  );
  expect((await ok(owner.GET('/me'))).id).toBe(me.id);
  await session.context.close();
});
