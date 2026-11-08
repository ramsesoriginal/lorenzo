import { expect, test } from '@playwright/test';
import { newCampaign, newLibrary, newUser, openLibrary, signedInPage } from './support';

// Appearance (D22, ADR 0416, screen 33): the account menu opens a dialog for the theme, the density of
// lists and tables, and motion; each is applied at once, kept on the device and there on the next page.

async function openAppearance(page: import('@playwright/test').Page) {
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('menuitem', { name: 'Appearance…' }).click();

  const dialog = page.getByRole('dialog', { name: 'Appearance' });

  await expect(dialog).toBeVisible();

  return dialog;
}

test('the theme, the density and motion are chosen in Appearance, applied at once and kept', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);

  await newLibrary(owner.api);

  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 1440, height: 900 },
    colorScheme: 'light',
  });

  await page.goto('/');
  await expect(page.locator('[data-account-signed-in]')).toBeVisible();

  const dialog = await openAppearance(page);
  const rowHeight = () =>
    page
      .locator('.shell-app')
      .evaluate((el) => getComputedStyle(el).getPropertyValue('--row-h').trim());

  // What is there to choose, and what is chosen to begin with.
  await expect(dialog.getByRole('radio', { name: 'System' }).first()).toHaveAttribute(
    'aria-checked',
    'true',
  );
  await expect(dialog.getByRole('radio', { name: 'Comfortable' })).toHaveAttribute(
    'aria-checked',
    'true',
  );
  expect(await rowHeight()).toBe('48px');

  await dialog.getByRole('radio', { name: 'Dark' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await dialog.getByRole('radio', { name: 'Compact' }).click();
  expect(await rowHeight()).toBe('36px');
  await dialog.getByRole('radio', { name: 'Dense' }).click();
  expect(await rowHeight()).toBe('28px');
  await dialog.getByRole('radio', { name: 'Reduced' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'reduced');
  await dialog.getByRole('button', { name: 'Done' }).click();
  await expect(dialog).toBeHidden();

  // The next page starts with all three, from before it paints.
  await page.goto('/tenants/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('html')).toHaveAttribute('data-density', 'dense');
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'reduced');
  expect(await rowHeight()).toBe('28px');

  // And back to what the system and the defaults say.
  const again = await openAppearance(page);

  await expect(again.getByRole('radio', { name: 'Dark' })).toHaveAttribute('aria-checked', 'true');
  await again.getByRole('radio', { name: 'System' }).first().click();
  await again.getByRole('radio', { name: 'Comfortable' }).click();
  await again.getByRole('radio', { name: 'System' }).last().click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.locator('html')).not.toHaveAttribute('data-density', /.*/);
  await expect(page.locator('html')).not.toHaveAttribute('data-motion', /.*/);
  await context.close();
});

test('on a phone, density is not offered and every row is big enough', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);

  await newLibrary(owner.api);

  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 430, height: 900 },
  });

  await page.goto('/');
  await expect(page.locator('[data-account-signed-in]')).toBeVisible();

  const dialog = await openAppearance(page);

  await expect(dialog.getByRole('radiogroup', { name: 'Theme' })).toBeVisible();
  await expect(dialog.getByRole('radiogroup', { name: 'Density of lists and tables' })).toHaveCount(
    0,
  );
  await context.close();
});

test('the rows of a list follow the density, and the controls and gutters do not', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);

  await newCampaign(owner.api, library.id, 'Harbour job');

  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 1440, height: 900 },
  });

  await openLibrary(page, library);

  await page.getByRole('tab', { name: 'People' }).first().click();

  const rows = page.locator('.shell-page .list > li:visible');

  await expect(rows.first()).toBeVisible();

  // The least tall row of the page is the density's row height, whatever it holds.
  const least = async () =>
    Math.round(
      await rows.evaluateAll((els) =>
        Math.min(...els.map((e) => e.getBoundingClientRect().height)),
      ),
    );
  const dialog = await openAppearance(page);
  const seen: number[] = [];

  for (const name of ['Comfortable', 'Compact', 'Dense']) {
    await dialog.getByRole('radio', { name }).click();
    seen.push(await least());
  }

  // Comfortable is the 48px row. Compact and Dense are lower, down to what the row's own controls
  // (a button, a select) need: a row never squeezes what is pressed in it.
  expect(seen[0]).toBe(48);
  expect(seen[1]).toBeLessThan(seen[0] ?? 0);
  expect(seen[1]).toBeLessThanOrEqual(42);
  expect(seen[2]).toBeLessThanOrEqual(seen[1] ?? 0);

  // The gutters of the page are the same at every density: it changes a row, not the page.
  expect(
    await page.locator('#content > .shell-page').evaluate((el) => getComputedStyle(el).paddingLeft),
  ).toBe('24px');
  await context.close();
});
