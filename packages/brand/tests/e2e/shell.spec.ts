import { expect, test } from '@playwright/test';
import { collectErrors } from './support';

test.describe('the shell follows the width of its container, not the window', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/preview/shell.html');
  });

  test('full width: the app bar, the palette button and the drawer; no tab bar', async ({ page }) => {
    await expect(page.locator('#frame .shell-apps')).toBeVisible();
    await expect(page.locator('#frame .palette-btn')).toBeVisible();
    await expect(page.locator('#frame .shell-tabbar')).toBeHidden();
    await expect(page.locator('#frame .shell-field-btn').first()).toHaveCSS('min-height', '36px');
  });

  test('a 430px frame in a wide window is a phone: tab bar, 44px controls, no app bar', async ({ page }) => {
    await page.click('[data-w="430"]');
    await expect(page.locator('#frame .shell-apps')).toBeHidden();
    await expect(page.locator('#frame .palette-btn')).toBeHidden();
    await expect(page.locator('#frame .shell-tabbar')).toBeVisible();
    expect((await page.locator('#frame .shell-bar .shell-field-btn').first().boundingBox())?.height).toBeGreaterThanOrEqual(44);
    expect((await page.locator('#frame .shell-tabbar a').first().boundingBox())?.height).toBeGreaterThanOrEqual(44);
  });

  test('a 900px frame is a tablet: the app bar, no tab bar', async ({ page }) => {
    await page.click('[data-w="900"]');
    await expect(page.locator('#frame .shell-apps')).toBeVisible();
    await expect(page.locator('#frame .shell-tabbar')).toBeHidden();
  });

  test('the state strip opens only when there is something to say, and closes to nothing', async ({ page }) => {
    await expect(page.locator('.shell-strip')).toHaveAttribute('data-open', '');
    await page.click('#strip-close');
    await expect.poll(async () => (await page.locator('.shell-strip').boundingBox())?.height ?? 0).toBeLessThan(2);
  });

  test('every state chip has an icon, a word and a pattern', async ({ page }) => {
    const chips = page.locator('.state-chip');
    expect(await chips.count()).toBe(4);
    for (const state of ['waiting', 'stale', 'conflict']) {
      const image = await page.locator(`.state-chip[data-state="${state}"]`).evaluate((e) => getComputedStyle(e).backgroundImage);
      expect(image, state).toContain('gradient');
    }
    for (let i = 0; i < 4; i++) {
      await expect(chips.nth(i).locator('svg')).toBeVisible();
      expect((await chips.nth(i).textContent())?.trim().length).toBeGreaterThan(0);
    }
  });
});

test.describe('the palette', () => {
  test('a dialog with a preview pane on a desktop, closed with Escape', async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto('/preview/shell.html');
    await page.click('#open-palette');
    const palette = page.locator('#palette');
    await expect(palette).toBeVisible();
    const box = await palette.boundingBox();
    expect(box?.width).toBeGreaterThan(900);
    expect(box?.width).toBeLessThanOrEqual(940);
    await expect(page.locator('.p-prev')).toBeVisible();
    await expect(page.locator('.p-opt[aria-selected="true"]')).toHaveCount(1);
    await page.keyboard.press('Escape');
    await expect(palette).toBeHidden();
    expect(errors).toEqual([]);
  });

  test('a full screen on a phone, with no preview pane', async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 900 });
    await page.goto('/preview/shell.html');
    await page.evaluate(() => (document.getElementById('palette') as HTMLDialogElement).showModal());
    const box = await page.locator('#palette').boundingBox();
    expect(box?.y).toBeLessThan(2);
    expect(box?.height).toBeGreaterThanOrEqual(890);
    await expect(page.locator('.p-prev')).toBeHidden();
    await expect(page.locator('.p-foot')).toBeHidden();
  });
});
