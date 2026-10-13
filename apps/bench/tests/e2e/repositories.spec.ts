import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test.describe('the repository menu and start screen', () => {
  test('the menu names the open repository, with the others and a way to see them all', async ({
    page,
  }) => {
    const button = page.getByRole('button', { name: /^Repository: Sample repository/ });
    await button.click();
    await expect(page.getByRole('menuitemradio', { name: /Sample repository/ })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    await page.keyboard.press('ArrowDown');
    await expect(page.getByRole('menuitem', { name: 'Your repositories…' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('menu')).toHaveCount(0);
    await expect(button).toBeFocused();
  });

  test('Your repositories… lists them with the role, and the open one says so', async ({
    page,
  }) => {
    await page.getByRole('button', { name: /^Repository:/ }).click();
    await page.getByRole('menuitem', { name: 'Your repositories…' }).click();
    const dialog = page.getByRole('dialog', { name: 'Your repositories' });
    await expect(dialog).toContainText('Sample repository');
    await expect(dialog).toContainText('Owner');
    await expect(dialog.getByRole('button', { name: 'Open Sample repository' })).toBeDisabled();
    await dialog.getByRole('button', { name: 'Close' }).click();
    await expect(dialog).toHaveCount(0);
  });
});

test.describe('the welcome', () => {
  test('is shown on the first visit, once dismissed stays away, and can be shown again', async ({
    page,
  }) => {
    const welcome = page.getByRole('region', { name: 'Welcome to Bench' });
    await expect(welcome).toBeVisible();
    await welcome.getByRole('button', { name: 'Got it' }).click();
    await expect(welcome).toBeHidden();
    await page.reload();
    await expect(page.locator('[data-tab="explorer"]')).toBeVisible();
    await expect(welcome).toBeHidden();
    await page.keyboard.press('Control+k');
    await page.getByLabel('Command palette').fill('show the welcome');
    await page.keyboard.press('Enter');
    await expect(welcome).toBeVisible();
  });
});
