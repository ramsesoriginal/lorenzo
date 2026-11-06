import { expect, test } from '@playwright/test';
import { collectErrors } from './support';

test.beforeEach(async ({ page }) => {
  await page.goto('/preview/pages.html');
});

test('the save bar opens on a change, counts, rewrites its buttons only when the count changes, and closes on Save', async ({ page }) => {
  const errors = collectErrors(page);
  const bar = page.locator('#save-bar');
  await expect.poll(async () => (await bar.boundingBox())?.height ?? 0).toBeLessThan(2);

  await page.click('#make-change');
  await expect(page.locator('#sb-text')).toHaveText('1 change not saved');
  await expect.poll(async () => (await bar.boundingBox())?.height ?? 0).toBeGreaterThan(30);

  // Rendering again with the same count must leave the buttons alone (a click that follows an edit
  // would otherwise be lost); a different count rewrites them.
  const saveBefore = await page.locator('#sb-save').elementHandle();
  await page.evaluate(() => (window as unknown as { renderSaveBar: () => void }).renderSaveBar());
  expect(await saveBefore?.evaluate((e) => e.isConnected)).toBe(true);
  await page.click('#make-change');
  await expect(page.locator('#sb-text')).toHaveText('2 changes not saved');
  expect(await saveBefore?.evaluate((e) => e.isConnected)).toBe(false);

  await page.click('#sb-save');
  await expect.poll(async () => (await bar.boundingBox())?.height ?? 0).toBeLessThan(2);
  expect(errors).toEqual([]);
});

test('density: 48, 36 and 28px rows; 64px in a phone-sized container', async ({ page }) => {
  const row = async () => (await page.locator('.demo-row').first().boundingBox())?.height;
  expect(await row()).toBeCloseTo(48, 0);
  await page.click('[data-d="compact"]');
  expect(await row()).toBeCloseTo(36, 0);
  await page.click('[data-d="dense"]');
  expect(await row()).toBeCloseTo(28, 0);
  // A container of phone width: every level is at least 44px, here the 64px row.
  await page.setViewportSize({ width: 430, height: 900 });
  await page.click('[data-d="comfortable"]');
  expect(await row()).toBeCloseTo(64, 0);
});

test('skeleton rows are as tall as a real row and pulse', async ({ page }) => {
  await expect(page.locator('.skeleton-row')).toHaveCount(5);
  expect((await page.locator('.skeleton-row').first().boundingBox())?.height).toBeCloseTo(48, 0);
  await expect(page.locator('.skeleton').first()).toHaveCSS('animation-name', 'brand-skeleton-pulse');
});

test('the sideways fade masks a row that scrolls', async ({ page }) => {
  const mask = page.locator('#hm');
  expect(await mask.evaluate((e) => (getComputedStyle(e).maskImage || getComputedStyle(e).webkitMaskImage))).toContain('linear-gradient');
  expect(await mask.evaluate((e) => e.scrollWidth > e.clientWidth)).toBe(true);
});

test('page widths: reading 680, form 1040', async ({ page }) => {
  expect((await page.locator('.shell-page--reading').boundingBox())?.width).toBeCloseTo(680, 0);
  expect((await page.locator('.shell-page--form').boundingBox())?.width).toBeCloseTo(1040, 0);
});

test('container steps: phone to 720, tablet from 721, desktop from 1100, large from 1700', async ({ page }) => {
  await page.setViewportSize({ width: 1900, height: 900 });
  const name = page.locator('#step-name');
  const label = () => name.evaluate((e) => getComputedStyle(e, '::before').content);
  for (const [width, expected] of [
    ['430', 'phone'],
    ['900', 'tablet'],
    ['1280', 'desktop'],
    ['1800', 'large'],
  ] as const) {
    await page.click(`[data-sw="${width}"]`);
    expect(await label()).toContain(expected);
  }
  // The edges of the steps.
  await page.evaluate(() => ((document.getElementById('steps-frame') as HTMLElement).style.width = '720px'));
  expect(await label()).toContain('phone');
  await page.evaluate(() => ((document.getElementById('steps-frame') as HTMLElement).style.width = '721px'));
  expect(await label()).toContain('tablet');
  await page.evaluate(() => ((document.getElementById('steps-frame') as HTMLElement).style.width = '1100px'));
  expect(await label()).toContain('desktop');
  await page.evaluate(() => ((document.getElementById('steps-frame') as HTMLElement).style.width = '1700px'));
  expect(await label()).toContain('large');
});
