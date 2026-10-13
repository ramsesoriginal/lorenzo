import { expect, test } from '@playwright/test';

const groupOf = (page: import('@playwright/test').Page, pane: string) =>
  page.locator('.grp', { has: page.locator(`[data-tab="${pane}"]`) });

/** The box of an element, once it has one (the page may be drawing it again). */
const boxOf = async (loc: import('@playwright/test').Locator) => {
  await expect.poll(async () => (await loc.boundingBox()) !== null).toBe(true);
  return (await loc.boundingBox()) as NonNullable<Awaited<ReturnType<typeof loc.boundingBox>>>;
};

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => {
    localStorage.clear();
    // The welcome strip appears late and moves the page; it has its own tests.
    localStorage.setItem('bench:welcomed', '1');
  });
  await page.reload();
});

test('opens with the explorer, an entry, and stats and parents', async ({ page }) => {
  for (const p of ['explorer', 'entry', 'props', 'links'])
    await expect(page.locator(`[data-tab="${p}"]`)).toBeVisible();
  await expect(page.locator('.entry-name')).toHaveValue('Monster');
});

test('picking an entry in the explorer shows it', async ({ page }) => {
  // Ghoul has two parents, so the tree has a row for it in each place.
  await page.getByRole('button', { name: 'Ghoul' }).first().click();
  await page.getByRole('tab', { name: 'Links' }).click();
  await expect(page.locator('.entry-name')).toHaveValue('Ghoul');
  await expect(page.locator('.pane-links')).toContainText('Undead');
  await expect(page.locator('.pane-links')).toContainText('Beast');
});

test('a one-tab group has a title line, and clicking a tab switches it', async ({ page }) => {
  await expect(groupOf(page, 'explorer').locator('.bar')).toHaveClass(/solo/);
  await page.getByRole('tab', { name: 'Links' }).click();
  await expect(page.locator('.pane-links')).toBeVisible();
  await expect(page.locator('.pane-props')).toHaveCount(0);
});

test('dragging a tab to the bottom edge of another group splits it', async ({ page }) => {
  const tab = page.locator('[data-tab="links"] .name');
  const target = groupOf(page, 'entry');
  await expect(target).toBeVisible();
  await expect(tab).toBeVisible();
  const box = await boxOf(target);
  const from = await boxOf(tab);
  await page.mouse.move(from.x + 10, from.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height - 10, { steps: 8 });
  await expect(page.locator('.drop')).toBeVisible();
  await page.mouse.up();
  const entry = await boxOf(groupOf(page, 'entry'));
  const links = await boxOf(groupOf(page, 'links'));
  expect(links.y).toBeGreaterThan(entry.y + entry.height - 2);
  // the stats tab it left is still in its old group, now alone
  await expect(groupOf(page, 'props').locator('.bar')).toHaveClass(/solo/);
});

test('dragging a tab into empty space floats it, and Dock puts it back', async ({ page }) => {
  const tab = page.locator('[data-tab="props"] .name');
  await expect(tab).toBeVisible();
  const from = await boxOf(tab);
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
  await expect(page.locator('[data-tab="explorer"]')).toBeVisible();
  await expect(page.locator('.divider').first()).toBeVisible();
  const before = await boxOf(groupOf(page, 'explorer'));
  const d = await boxOf(page.locator('.divider').first());
  await page.mouse.move(d.x + d.width / 2, d.y + 200);
  await page.mouse.down();
  await page.mouse.move(d.x + d.width / 2 + 120, d.y + 200, { steps: 5 });
  await page.mouse.up();
  const after = await boxOf(groupOf(page, 'explorer'));
  expect(after.width).toBeGreaterThan(before.width + 100);
});

test('the layout is remembered across a reload', async ({ page }) => {
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('split entry to the bottom');
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Close Properties' }).click();
  await page.reload();
  await expect(page.locator('[data-tab="props"]')).toHaveCount(0);
  await expect(page.locator('[data-tab="entry"]')).toBeVisible();
});

test('the palette opens panes and entries, and Reset layout restores', async ({ page }) => {
  await page.getByRole('button', { name: 'Close Properties' }).click();
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('open properties');
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-tab="props"]')).toBeVisible();
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('zombie');
  await page.keyboard.press('Enter');
  await expect(page.locator('.entry-name')).toHaveValue('Zombie');
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('reset layout');
  await page.keyboard.press('Enter');
  await expect(page.locator('.grp')).toHaveCount(3);
});

test('tabs can be moved with the keyboard', async ({ page }) => {
  const tab = page.locator('[data-tab="props"] .name');
  await tab.focus();
  await page.keyboard.press('Alt+Shift+ArrowLeft');
  const a = await boxOf(groupOf(page, 'props'));
  const b = await boxOf(groupOf(page, 'links'));
  expect(a.x).toBeLessThan(b.x);
  await page.locator('[data-tab="links"] .name').focus();
  await page.keyboard.press('Alt+f');
  await expect(page.locator('.grp.float')).toHaveCount(1);
});

test('arrow keys go between the tabs of a group and choose the one they reach', async ({
  page,
}) => {
  await page.locator('[data-tab="props"] .name').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('[data-tab="links"] .name')).toBeFocused();
  await expect(page.locator('[data-tab="links"] .name')).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press('Home');
  await expect(page.locator('[data-tab="props"] .name')).toBeFocused();
});

test('Ctrl+Alt+arrow moves a tab into the group beside, and says so', async ({ page }) => {
  await page.locator('[data-tab="props"] .name').focus();
  await page.keyboard.press('Control+Alt+ArrowLeft');
  await expect(groupOf(page, 'props')).toHaveCount(1);
  expect(await groupOf(page, 'props').locator('[data-tab="entry"]').count()).toBe(1);
  await expect(
    page.locator('[role="status"]', { hasText: 'Properties moved to the group on the left.' }),
  ).toBeAttached();
});

test('Alt+D docks a floating tab back', async ({ page }) => {
  await page.locator('[data-tab="links"] .name').focus();
  await page.keyboard.press('Alt+f');
  await expect(page.locator('.grp.float')).toHaveCount(1);
  await page.locator('.grp.float [data-tab="links"] .name').focus();
  await page.keyboard.press('Alt+d');
  await expect(page.locator('.grp.float')).toHaveCount(0);
});

test('the palette lists the keyboard shortcuts for tabs', async ({ page }) => {
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('keyboard shortcuts');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toContainText('Ctrl + Alt + arrows');
});

test('the explorer draws each entry’s kind from the atlas, and the atlas is served', async ({
  page,
}) => {
  await page.goto('/');
  const use = page.locator('.explorer .row .ic use').first();
  await expect(use).toBeAttached();
  const href = (await use.getAttribute('href')) ?? '';
  expect(href).toMatch(/\.svg#icon-kind-/);
  const [file, symbol] = href.split('#');
  const served = await page.request.get(new URL(file ?? '', page.url()).toString());
  expect(served.ok()).toBe(true);
  expect(await served.text()).toContain(`id="${symbol}"`);
  // And it is drawn: the box has a size.
  const box = await page.locator('.explorer .row .ic').first().boundingBox();
  expect(box?.width).toBeGreaterThan(8);
});

test.describe('appearance', () => {
  const open = async (page: import('@playwright/test').Page) => {
    await page.getByRole('button', { name: 'Appearance' }).click();
    return page.getByRole('dialog', { name: 'Appearance' });
  };

  test('the theme is chosen from the popover and remembered across a reload', async ({ page }) => {
    const ap = await open(page);
    await ap.getByRole('group', { name: 'Theme' }).getByRole('button', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog', { name: 'Appearance' })).toHaveCount(0);
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  });

  test('System follows the device', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    const ap = await open(page);
    await ap.getByRole('group', { name: 'Theme' }).getByRole('button', { name: 'System' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.emulateMedia({ colorScheme: 'light' });
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  });
});

test.describe('the Write layout is a focused page', () => {
  const layout = (page: import('@playwright/test').Page, name: string) =>
    page.getByRole('group', { name: 'Layout' }).getByRole('button', { name });

  test('hides inheritance and notes, and only in Write', async ({ page }) => {
    await expect(page.locator('.pane-entry .entry-extra')).toBeVisible();
    await layout(page, 'Write').click();
    await expect(page.locator('.pane-entry .entry-extra')).toBeHidden();
    await expect(page.locator('.entry-name')).toBeVisible();
    await layout(page, 'Inspect').click();
    await expect(page.locator('.pane-entry .entry-extra')).toBeVisible();
  });
});
