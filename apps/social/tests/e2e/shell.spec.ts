import { expect, test } from '@playwright/test';
import { ok } from './support/api.ts';
import { signedIn, world } from './support/world.ts';

test('one library shows no switcher; with two the person can switch, and Home carries on to the last', async ({
  browser,
}) => {
  const one = await world();
  const alone = await signedIn(browser, one.subject);
  await alone.goto(`/webs/?tenant=${one.tenant.id}`);
  await expect(alone.getByRole('heading', { name: 'Webs', level: 1 })).toBeVisible();
  await expect(alone.locator('[data-library-switcher]')).toBeHidden();

  const w = await world();
  const other = await ok(w.gm.POST('/tenants', { body: { name: 'The other library' } }));
  const page = await signedIn(browser, w.subject);
  await page.goto(`/webs/?tenant=${w.tenant.id}`);
  const select = page.locator('[data-library-select]');
  await expect(select).toBeVisible();
  await select.selectOption(other.id);
  await expect(page).toHaveURL(new RegExp(`/webs/\\?tenant=${other.id}`));
  // Home carries on to the library last used, once that library's webs have opened.
  await expect(page.getByRole('heading', { name: 'Webs', level: 1 })).toBeVisible();
  await expect(page.getByText(/There are no webs you can see yet/)).toBeVisible();
  await page.goto('/');
  await expect(page).toHaveURL(new RegExp(`/webs/\\?tenant=${other.id}`));
});

test('Types and standings and Problems are tabs for those who write; a player sees Webs and Relationships', async ({
  browser,
}) => {
  const w = await world();
  const gm = await signedIn(browser, w.subject);
  await gm.goto(`/webs/?tenant=${w.tenant.id}`);
  const tabs = gm.getByRole('navigation').first();
  await expect(tabs.getByRole('link', { name: 'Types and standings' })).toBeVisible();
  await expect(tabs.getByRole('link', { name: 'Problems' })).toBeVisible();

  const player = await signedIn(browser, w.playerSubject);
  await player.goto(`/webs/?tenant=${w.tenant.id}`);
  const seen = player.getByRole('navigation').first();
  await expect(seen.getByRole('link', { name: 'Webs' })).toBeVisible();
  await expect(seen.getByRole('link', { name: 'Relationships' })).toBeVisible();
  await expect(seen.getByRole('link', { name: 'Types and standings' })).toBeHidden();
  await expect(seen.getByRole('link', { name: 'Problems' })).toBeHidden();
});
