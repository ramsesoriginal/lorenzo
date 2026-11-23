// The notification bell of the shell's header (ADR 0265, ADR 0423): the unread count, which links to the
// account hub's notifications, where they are read.
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
  page.getByRole('link', { name: /^Notifications/ });

test('the bell counts what is unread and links to the hub, where they are read', async ({
  world,
  as,
}) => {
  await tell(world, 'The bridge collapsed', 'Ashfang saw it fall.');
  await tell(world, 'A raven arrived', 'It carried a sealed letter.');

  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);

  await expect(bell(page)).toHaveAccessibleName('Notifications, 2 unread');
  await expect(bell(page)).toHaveAttribute('href', /\/notifications\/$/);
});

test('with nothing unread the bell has no count', async ({ world, as }) => {
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}`);

  await expect(bell(page)).toHaveAccessibleName('Notifications');
});

test('the bell stays quiet when notifications cannot be loaded', async ({ world, as }) => {
  const page = await as(world.pia);

  await page.route('**/me/notifications*', (route) => route.abort());
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
  await expect(bell(page)).toBeHidden();
});

test('a signed-out page has no bell and asks for nothing', async ({ page }) => {
  const asked: string[] = [];

  page.on('request', (request) => {
    if (request.url().includes('/me/notifications')) asked.push(request.url());
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();
  await expect(bell(page)).toBeHidden();
  expect(asked).toEqual([]);
});
