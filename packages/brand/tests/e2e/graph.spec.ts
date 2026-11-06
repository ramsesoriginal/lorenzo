import { expect, test } from '@playwright/test';
import { collectErrors } from './support';

test.beforeEach(async ({ page }) => {
  await page.goto('/preview/graph.html');
});

test('a standing is a number, a quiet bar and a mark and a word; below zero is hatched', async ({ page }) => {
  const cells = page.locator('#standing .standing');
  expect(await cells.count()).toBe(6);
  for (let i = 0; i < 6; i++) {
    await expect(cells.nth(i).locator('.standing-num')).not.toBeEmpty();
    await expect(cells.nth(i).locator('.standing-mark')).not.toBeEmpty();
  }
  expect(await page.locator('#standing .standing-bar > i.neg').evaluate((e) => getComputedStyle(e).backgroundImage)).toContain('repeating-linear-gradient');
});

test('edges: solid is direct, dashed is derived, dotted is unknown', async ({ page }) => {
  const dash = await page.evaluate(() =>
    Object.fromEntries([...document.querySelectorAll('.graph-edge')].map((e) => [(e as HTMLElement).dataset.kind, getComputedStyle(e.querySelector('path:not(.hit)') as Element).strokeDasharray])),
  );
  expect(dash.direct).toBe('none');
  expect(dash.derived).not.toBe('none');
  expect(dash.unknown).not.toBe('none');
  expect(dash.derived).not.toBe(dash.unknown);
});

test('a selection is a fill and a heavier line, one at a time, from the mouse and the keyboard', async ({ page }) => {
  const errors = collectErrors(page);
  await page.locator('.graph-node[aria-label="Tobias"]').click();
  await expect(page.locator('.graph-node[aria-selected="true"]')).toHaveCount(1);
  await expect(page.locator('.graph-node[aria-label="Tobias"] circle')).toHaveCSS('stroke-width', '3px');
  await page.locator('.graph-node[aria-label="Mara"]').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.graph-node[aria-label="Mara"]')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('.graph-node[aria-selected="true"]')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('focus mode dims everything but the selection and its neighbours', async ({ page }) => {
  await page.click('#focus');
  await expect(page.locator('.graph-node[data-far]').first()).toHaveCSS('opacity', '0.2');
  await expect(page.locator('.graph-node[aria-label="Mara"]')).toHaveCSS('opacity', '1');
  await page.click('#focus');
  await expect(page.locator('.graph-node[data-far]').first()).toHaveCSS('opacity', '1');
});

test('a matrix cell can take focus and shows a ring; the diagonal is hatched', async ({ page }) => {
  await page.locator('.graph-matrix td[data-cell]').first().focus();
  await expect(page.locator('.graph-matrix td[data-cell]').first()).toHaveCSS('outline-style', 'solid');
  expect(await page.locator('.graph-matrix td.diag').first().evaluate((e) => getComputedStyle(e).backgroundImage)).toContain('repeating-linear-gradient');
});

test('the time filter has two handles that are buttons with names', async ({ page }) => {
  const handles = page.locator('.time-filter-handle');
  await expect(handles).toHaveCount(2);
  await expect(handles.first()).toHaveAttribute('aria-label', 'Start of the range');
  await expect(handles.nth(1)).toHaveAttribute('aria-label', 'End of the range');
});
