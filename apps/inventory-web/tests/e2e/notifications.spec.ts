// The notification bell in the header (ADR 0265): the unread badge, the dropdown, reading one
// or all, and where a notification leads.
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import type { World } from './support/world.ts';

/** The GM tells Pia's character something, as a game event the character's player gets. */
async function tell(world: World, title: string, body: string) {
  await ok(
    world.gm.api.POST('/tenants/{tenant_id}/characters/{character_id}/notifications', {
      params: {
        path: { tenant_id: world.tenantId, character_id: world.pia.character.entity_id },
      },
      body: { type: 'game_event', title, body, recipient_user_id: world.pia.userId },
    }),
  );
}

const bell = (page: import('@playwright/test').Page) =>
  page.getByRole('button', { name: /^Notifications/ });

test('the bell counts what is unread, lists it, and reads one, then all', async ({ world, as }) => {
  await tell(world, 'The bridge collapsed', 'Ashfang saw it fall.');
  await tell(world, 'A raven arrived', 'It carried a sealed letter.');

  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);

  await expect(bell(page)).toHaveAccessibleName('Notifications, 2 unread');
  await expect(bell(page)).toHaveAttribute('aria-expanded', 'false');

  await bell(page).click();
  await expect(bell(page)).toHaveAttribute('aria-expanded', 'true');
  const panel = page.getByRole('group', { name: 'Notifications' });
  await expect(panel.getByText('The bridge collapsed')).toBeVisible();
  await expect(panel.getByText('Ashfang saw it fall.')).toBeVisible();
  await expect(panel.getByText('A raven arrived')).toBeVisible();

  // One read.
  await panel.getByRole('button', { name: 'Mark read: A raven arrived' }).click();
  await expect(bell(page)).toHaveAccessibleName('Notifications, 1 unread');
  await expect(panel.getByRole('button', { name: /^Mark read:/ })).toHaveCount(1);

  // All read.
  await panel.getByRole('button', { name: 'Mark all as read' }).click();
  await expect(bell(page)).toHaveAccessibleName('Notifications, none unread');
  await expect(panel.getByRole('button', { name: 'Mark all as read' })).toBeHidden();
  await expect(panel.getByText('The bridge collapsed')).toBeVisible();

  // Escape closes it and gives the focus back.
  await page.keyboard.press('Escape');
  await expect(panel).toBeHidden();
  await expect(bell(page)).toBeFocused();
});

test('a notification about a character leads to its board; See all leads to the hub', async ({
  world,
  as,
}) => {
  await tell(world, 'The bridge collapsed', 'Ashfang saw it fall.');

  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await bell(page).click();
  const panel = page.getByRole('group', { name: 'Notifications' });

  await expect(panel.getByRole('link', { name: 'See all' })).toHaveAttribute(
    'href',
    /\/notifications\/$/,
  );

  await panel.getByRole('link', { name: 'The bridge collapsed' }).click();
  await expect(page).toHaveURL(
    new RegExp(`/board/\\?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`),
  );
});

test('the bell says so when notifications cannot be loaded', async ({ world, as }) => {
  const page = await as(world.pia);

  await page.route('**/me/notifications*', (route) => route.abort());
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await bell(page).click();
  await expect(page.getByText('Could not load notifications.')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('group', { name: 'Notifications' })).toBeHidden();
});

test('a signed-out page has no bell and asks for nothing', async ({ page }) => {
  const asked: string[] = [];

  page.on('request', (request) => {
    if (request.url().includes('/me/notifications')) asked.push(request.url());
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();
  await expect(page.getByRole('button', { name: /^Notifications/ })).toBeHidden();
  expect(asked).toEqual([]);
});
