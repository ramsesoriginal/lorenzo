import { expect, test } from '@playwright/test';
import { newLibrary, newUser, signedInPage } from './support';

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
