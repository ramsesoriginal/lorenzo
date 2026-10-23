import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { type Browser, expect, test } from '@playwright/test';
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

/** A library with a GM, and a player in one of its campaigns. */
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
  return { subject, gm, tenant, player, playerSubject, path };
}

test('a GM builds a tree of Locations and a player sees only what is visible', async ({
  browser,
}) => {
  const w = await world();
  const gm = await signedIn(browser, w.subject);
  const player = await signedIn(browser, w.playerSubject);
  try {
    await gm.goto('/');
    await gm.getByRole('link', { name: w.tenant.name, exact: true }).click();
    await expect(gm.getByRole('heading', { name: 'Locations', exact: true })).toBeVisible();
    await expect(gm.getByText('No Locations yet.')).toBeVisible();

    // A top-level Location, visible to everyone.
    await gm.getByLabel('Name', { exact: true }).fill('Realm');
    await gm.getByLabel('Link name (optional)').fill('realm');
    await gm.getByLabel('Visible to everyone in the library').check();
    await gm.getByRole('button', { name: 'Add Location', exact: true }).click();
    await expect(gm.getByRole('heading', { name: 'Realm', exact: true })).toBeVisible();

    // A part of it that is restricted, and a part of that, visible to everyone.
    await gm.getByLabel('Name', { exact: true }).fill('Secret hold');
    await gm.getByRole('button', { name: 'Add Location', exact: true }).click();
    await expect(gm.getByRole('heading', { name: 'Secret hold', exact: true })).toBeVisible();
    await expect(gm.getByText('Restricted')).toBeVisible();
    await gm.getByLabel('Name', { exact: true }).fill('Camp');
    await gm.getByLabel('Visible to everyone in the library').check();
    await gm.getByRole('button', { name: 'Add Location', exact: true }).click();
    await expect(gm.getByRole('heading', { name: 'Camp', exact: true })).toBeVisible();
    await expect(gm.getByRole('link', { name: 'In Secret hold' })).toBeVisible();

    // The GM can rename it, and the page says so.
    await gm.getByLabel('Rename this Location').fill('Base camp');
    await gm.getByRole('button', { name: 'Save name', exact: true }).click();
    await expect(gm.getByRole('heading', { name: 'Base camp', exact: true })).toBeVisible();

    // The player: the Realm, with the Base camp straight inside it, and no trace of the hold.
    await player.goto(`/locations/?tenant=${w.tenant.id}`);
    await expect(player.getByRole('link', { name: 'Realm', exact: true })).toBeVisible();
    await expect(player.getByRole('button', { name: 'Add Location' })).toHaveCount(0);
    await player.getByRole('button', { name: 'Show what is inside Realm' }).click();
    await expect(player.getByRole('link', { name: 'Base camp', exact: true })).toBeVisible();
    await expect(player.getByText('Secret hold')).toHaveCount(0);
    await player.getByRole('link', { name: 'Base camp', exact: true }).click();
    await expect(player.getByRole('link', { name: 'In Realm' })).toBeVisible();
    await expect(player.getByText('Secret hold')).toHaveCount(0);
    await expect(player.getByRole('button', { name: 'Save name' })).toHaveCount(0);

    // Opening the hold for everyone shows it to the player, and the camp moves under it.
    await gm.goto(`/location/?tenant=${w.tenant.id}&slug=realm`);
    await gm.getByRole('button', { name: 'Show what is inside Secret hold' }).click();
    await gm.getByRole('link', { name: 'Secret hold', exact: true }).click();
    // The Realm page has the same controls: wait for the page that was asked for.
    await expect(gm.getByRole('heading', { name: 'Secret hold', exact: true })).toBeVisible();
    await gm.getByLabel('Everyone in the library can see this Location').check();
    await gm.getByRole('button', { name: 'Save visibility' }).click();
    await expect(gm.getByText('Visible to everyone', { exact: true })).toBeVisible();
    await player.goto(`/locations/?tenant=${w.tenant.id}`);
    await player.getByRole('button', { name: 'Show what is inside Realm' }).click();
    await expect(player.getByRole('link', { name: 'Secret hold', exact: true })).toBeVisible();
  } finally {
    await gm.context().close();
    await player.context().close();
  }
});

test('a Location refuses to become part of itself and the pages have no accessibility errors', async ({
  browser,
}) => {
  const w = await world();
  const gm = await signedIn(browser, w.subject, 'dark');
  try {
    const top = await ok(
      w.gm.POST('/tenants/{tenant_id}/locations', {
        params: { path: w.path },
        body: { name: 'Top', is_public: true },
      }),
    );
    const inner = await ok(
      w.gm.POST('/tenants/{tenant_id}/locations', {
        params: { path: w.path },
        body: { name: 'Inner', is_public: true, parent_id: top.id },
      }),
    );
    await gm.goto(`/location/?tenant=${w.tenant.id}&id=${top.id}`);
    await expect(gm.getByRole('heading', { name: 'Top', exact: true })).toBeVisible();
    await gm.getByLabel('Move it into (type a name)').fill('Inner');
    await gm.getByLabel('Locations that match').selectOption({ label: 'Inner' });
    await gm.getByRole('button', { name: 'Move here', exact: true }).click();
    await expect(gm.getByRole('alert')).toBeVisible();
    await expect(gm.getByRole('alert')).not.toContainText(inner.id);
    for (const address of [
      '/',
      `/locations/?tenant=${w.tenant.id}`,
      `/location/?tenant=${w.tenant.id}&id=${top.id}`,
    ]) {
      await gm.goto(address);
      await expect(gm.locator('[data-page]')).toBeVisible();
      await expect(gm.locator('[data-loading]')).toHaveCount(0);
      const result = await new AxeBuilder({ page: gm }).analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
    }
  } finally {
    await gm.context().close();
  }
});
