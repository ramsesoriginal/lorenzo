import { expect, test } from '@playwright/test';

const groupOf = (page: import('@playwright/test').Page, pane: string) =>
  page.locator('.grp', { has: page.locator(`[data-tab="${pane}"]`) });

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test('opens with the explorer, an entry, and stats and parents', async ({ page }) => {
  for (const p of ['explorer', 'entry', 'props', 'links'])
    await expect(page.locator(`[data-tab="${p}"]`)).toBeVisible();
  await expect(page.locator('.pane-entry h1')).toHaveText('Wolf');
});

test('picking an entry in the explorer shows it', async ({ page }) => {
  await page.getByRole('button', { name: 'Ghoul' }).click();
  await page.getByRole('tab', { name: 'Parents and children' }).click();
  await expect(page.locator('.pane-entry h1')).toHaveText('Ghoul');
  await expect(page.locator('.pane-links')).toContainText('Undead');
  await expect(page.locator('.pane-links')).toContainText('Beast');
});

test('a one-tab group has a title line, and clicking a tab switches it', async ({ page }) => {
  await expect(groupOf(page, 'explorer').locator('.bar')).toHaveClass(/solo/);
  await page.getByRole('tab', { name: 'Parents and children' }).click();
  await expect(page.locator('.pane-links')).toBeVisible();
  await expect(page.locator('.pane-props')).toHaveCount(0);
});

test('dragging a tab to the bottom edge of another group splits it', async ({ page }) => {
  const tab = page.locator('[data-tab="links"] .name');
  const target = groupOf(page, 'entry');
  const box = (await target.boundingBox())!;
  const from = (await tab.boundingBox())!;
  await page.mouse.move(from.x + 10, from.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height - 10, { steps: 8 });
  await expect(page.locator('.drop')).toBeVisible();
  await page.mouse.up();
  const entry = (await groupOf(page, 'entry').boundingBox())!;
  const links = (await groupOf(page, 'links').boundingBox())!;
  expect(links.y).toBeGreaterThan(entry.y + entry.height - 2);
  // the stats tab it left is still in its old group, now alone
  await expect(groupOf(page, 'props').locator('.bar')).toHaveClass(/solo/);
});

test('dragging a tab into empty space floats it, and Dock puts it back', async ({ page }) => {
  const tab = page.locator('[data-tab="props"] .name');
  const from = (await tab.boundingBox())!;
  // dropping on the title bar's own group would re-tab it; drag over the top bar instead
  await page.mouse.move(from.x + 10, from.y + 10);
  await page.mouse.down();
  await page.mouse.move(700, 4, { steps: 8 });
  await page.mouse.up();
  await expect(page.locator('.grp.float')).toHaveCount(1);
  await page.getByRole('button', { name: 'Dock' }).click();
  await expect(page.locator('.grp.float')).toHaveCount(0);
  await expect(page.locator('[data-tab="props"]')).toBeVisible();
});

test('a divider can be dragged', async ({ page }) => {
  const before = (await groupOf(page, 'explorer').boundingBox())!;
  const d = (await page.locator('.divider').first().boundingBox())!;
  await page.mouse.move(d.x + d.width / 2, d.y + 200);
  await page.mouse.down();
  await page.mouse.move(d.x + d.width / 2 + 120, d.y + 200, { steps: 5 });
  await page.mouse.up();
  const after = (await groupOf(page, 'explorer').boundingBox())!;
  expect(after.width).toBeGreaterThan(before.width + 100);
});

test('the layout is remembered across a reload', async ({ page }) => {
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('split entry to the bottom');
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Close Stats' }).click();
  await page.reload();
  await expect(page.locator('[data-tab="props"]')).toHaveCount(0);
  await expect(page.locator('[data-tab="entry"]')).toBeVisible();
});

test('the palette opens panes and entries, and Reset layout restores', async ({ page }) => {
  await page.getByRole('button', { name: 'Close Stats' }).click();
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('open stats');
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-tab="props"]')).toBeVisible();
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('zombie');
  await page.keyboard.press('Enter');
  await expect(page.locator('.pane-entry h1')).toHaveText('Zombie');
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('reset layout');
  await page.keyboard.press('Enter');
  await expect(page.locator('.grp')).toHaveCount(3);
});

test('tabs can be moved with the keyboard', async ({ page }) => {
  const tab = page.locator('[data-tab="props"] .name');
  await tab.focus();
  await page.keyboard.press('Alt+Shift+ArrowLeft');
  const a = (await groupOf(page, 'props').boundingBox())!;
  const b = (await groupOf(page, 'links').boundingBox())!;
  expect(a.x).toBeLessThan(b.x);
  await page.locator('[data-tab="links"] .name').focus();
  await page.keyboard.press('Alt+f');
  await expect(page.locator('.grp.float')).toHaveCount(1);
});
