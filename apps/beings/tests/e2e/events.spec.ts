import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';

test('staff see ordered participating Event titles below Inventory; players and opt-outs do not query them', async ({
  world,
  as,
}) => {
  const api = world.gm.api;
  const tenant_id = world.tenantId;
  const make = (name: string, slug: string) =>
    ok(
      api.POST('/tenants/{tenant_id}/entities', {
        params: { path: { tenant_id } },
        body: { name, slug, kinds: ['event'], parents: [] },
      }),
    );
  const first = await make('Departure', 'departure');
  const middle = await make('Crossing', 'crossing');
  const last = await make('Arrival', 'arrival');
  for (const [left, right] of [
    [first, middle],
    [middle, last],
  ]) {
    const path = { tenant_id, event_id: left.id };
    const saved = await api.GET('/tenants/{tenant_id}/events/{event_id}/relationships', {
      params: { path },
    });
    await ok(
      api.PUT('/tenants/{tenant_id}/events/{event_id}/relationships/{other_event_id}', {
        params: {
          path: { ...path, other_event_id: right.id },
          header: { 'if-match': saved.response.headers.get('etag') ?? '' },
        },
        body: { kind: 'causes', direction: 'outgoing' },
      }),
    );
  }
  for (const event of [first, last]) {
    const path = { tenant_id, event_id: event.id };
    const saved = await api.GET('/tenants/{tenant_id}/events/{event_id}/participants', {
      params: { path },
    });
    await ok(
      api.PUT('/tenants/{tenant_id}/events/{event_id}/participants/{being_id}', {
        params: {
          path: { ...path, being_id: world.pia.character.entity_id },
          header: { 'if-match': saved.response.headers.get('etag') ?? '' },
        },
      }),
    );
  }
  const page = await as(world.gm);
  await page.goto(`/being/?tenant=${tenant_id}&id=${world.pia.character.entity_id}`);
  const events = page.locator('[data-being-events]');
  await expect(events).toBeVisible();
  await expect(events.locator('li a')).toHaveText(['Departure', 'Arrival']);
  await expect(events).toContainText('Causal');
  await expect(events.locator('li a').first()).toHaveAttribute(
    'href',
    /\/entry\/\?tenant=.*&slug=departure/,
  );
  expect(
    await page
      .locator('#inventory')
      .evaluate((inventory) =>
        Boolean(inventory.nextElementSibling?.matches('[data-being-events]')),
      ),
  ).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const player = await as(world.pia);
  const orderReads: string[] = [];
  player.on('request', (r) => {
    if (r.url().includes('/events?')) orderReads.push(r.url());
  });
  await player.goto(`/being/?tenant=${tenant_id}&id=${world.pia.character.entity_id}`);
  await expect(player.getByRole('heading', { name: 'Ashfang', level: 1 })).toBeVisible();
  await expect(player.locator('[data-being-events]')).toBeHidden();
  expect(orderReads).toEqual([]);
  await ok(
    api.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out', {
      params: { path: { tenant_id, campaign_id: world.campaignId } },
    }),
  );
  const optOutReads: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/events?')) optOutReads.push(r.url());
  });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Ashfang', level: 1 })).toBeVisible();
  await expect(page.locator('[data-being-events]')).toBeHidden();
  expect(optOutReads).toEqual([]);
});
