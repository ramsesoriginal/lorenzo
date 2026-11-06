import { expect, test } from '@playwright/test';

test.describe('dialogs', () => {
  test('a closed dialog is not on the page; on a desktop it opens centred, without a grip', async ({ page }) => {
    await page.goto('/preview/dialogs.html');
    await expect(page.locator('#sheet-dialog')).toBeHidden();
    await page.click('#open-sheet');
    const box = await page.locator('#sheet-dialog').boundingBox();
    expect(box?.width).toBeLessThanOrEqual(480);
    expect(box?.y).toBeGreaterThan(20);
    await expect(page.locator('#sheet-dialog .sheet-grip')).toBeHidden();
  });

  test('on a phone a dialog is a bottom sheet: full width, a grip, 44px stacked actions', async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 900 });
    await page.goto('/preview/dialogs.html');
    await page.click('#open-sheet');
    const box = await page.locator('#sheet-dialog').boundingBox();
    const view = await page.evaluate(() => window.innerWidth);
    expect(box?.x).toBe(0);
    // Full width, give or take a classic scrollbar (15px); a phone's is an overlay.
    expect(box?.width).toBeGreaterThanOrEqual(view - 16);
    // The box is its final box as soon as it opens: it does not slide.
    expect((box?.y ?? 0) + (box?.height ?? 0)).toBeCloseTo(900, 0);
    await expect(page.locator('#sheet-dialog .sheet-grip')).toBeVisible();
    const action = await page.locator('#sheet-dialog .dialog-actions button').first().boundingBox();
    expect(action?.height).toBeGreaterThanOrEqual(44);
    expect(action?.width).toBeGreaterThan(view - 60);
  });

  test('a native close is instant: a dialog can be reopened at once', async ({ page }) => {
    await page.goto('/preview/forms.html');
    // The award dialog on the dialogs page closes from a form; here use close() directly.
    await page.goto('/preview/dialogs.html');
    await page.evaluate(() => {
      const d = document.getElementById('sheet-dialog') as HTMLDialogElement;
      d.showModal();
      d.close();
      d.showModal();
    });
    await expect(page.locator('#sheet-dialog')).toBeVisible();
  });

  test('data-closing fades a dialog out, and a reopen in the meantime wins', async ({ page }) => {
    await page.goto('/preview/dialogs.html');
    await page.click('#open-sheet');
    await page.keyboard.press('Escape'); // the preview turns Escape into the closing fade
    await expect(page.locator('#sheet-dialog')).toHaveAttribute('data-closing', '');
    await expect(page.locator('#sheet-dialog')).toBeVisible();
    await expect(page.locator('#sheet-dialog')).toBeHidden();
    await expect(page.locator('#sheet-dialog')).not.toHaveAttribute('data-closing', '');
    // Close and reopen straight away.
    await page.evaluate(() => {
      const w = window as unknown as { openDialog: (d: HTMLElement) => void; closeDialog: (d: HTMLElement) => void };
      const d = document.getElementById('sheet-dialog') as HTMLElement;
      w.openDialog(d);
      w.closeDialog(d);
      w.openDialog(d);
    });
    await page.waitForTimeout(400);
    await expect(page.locator('#sheet-dialog')).toBeVisible();
    await expect(page.locator('#sheet-dialog')).not.toHaveAttribute('data-closing', '');
  });
});

test.describe('menus', () => {
  test('a menu on a phone with .as-sheet is a bottom sheet with 48px items', async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 900 });
    await page.goto('/preview/dialogs.html');
    await page.evaluate(() => document.querySelector('.menu')?.classList.add('as-sheet'));
    const menu = page.locator('.menu');
    await expect(menu).toHaveCSS('position', 'fixed');
    await expect(menu).toHaveCSS('border-top-left-radius', '16px');
    await expect(page.locator('.menu-item').first()).toHaveCSS('min-height', '48px');
  });
});

test.describe('toasts', () => {
  test('a timed toast leaves by itself; an error has no timer and stays until closed; Undo dismisses', async ({ page }) => {
    await page.goto('/preview/dialogs.html');
    await page.click('#toast-ok');
    await page.click('#toast-err');
    await page.click('#toast-undo');
    await expect(page.locator('.toast-card')).toHaveCount(3);
    await expect(page.locator('.toast-card[data-kind="error"] .toast-bar')).toHaveCount(0);
    await expect(page.locator('.toast-card[data-kind="ok"] .toast-bar')).toBeVisible();

    await page.locator('.toast-card[data-kind="undo"] .toast-action').click();
    await expect(page.locator('.toast-card[data-kind="undo"]')).toHaveCount(0);

    // The timed one is gone after its time; the error is still there.
    await expect(page.locator('.toast-card[data-kind="ok"]')).toHaveCount(0, { timeout: 8000 });
    await expect(page.locator('.toast-card[data-kind="error"]')).toHaveCount(1);
    await page.locator('.toast-card[data-kind="error"] button').click();
    await expect(page.locator('.toast-card')).toHaveCount(0);
  });

  test('the toast region is a polite live region', async ({ page }) => {
    await page.goto('/preview/dialogs.html');
    await expect(page.locator('.toast-region')).toHaveAttribute('role', 'status');
    await expect(page.locator('.toast-region')).toHaveAttribute('aria-live', 'polite');
  });
});
