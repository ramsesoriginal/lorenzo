import { expect, type Locator, type Page } from '@playwright/test';

/** The board's name, which says whose board it is. */
export const boardTitle = (page: Page) => page.locator('[data-board-title]');

/** The menu of the board's name (IN7). */
export async function openSwitcher(page: Page): Promise<void> {
  // The menu lists what has loaded when it opens, so wait for the board to say whose it is.
  await expect(boardTitle(page)).not.toBeEmpty();
  await page.locator('[data-switcher]').click();
}

/** Opens the board of one of the viewer's own characters or groups, from the board's name. */
export async function switchTo(page: Page, name: string): Promise<void> {
  await openSwitcher(page);
  await page
    .locator('[role^="menuitem"]')
    .filter({ hasText: new RegExp(`^\\s*${name}\\s*$`) })
    .click();
}

/** A GM's way to any being: opens the finder, which `browseBeing` and the raw-address test use. */
export async function openFinder(page: Page): Promise<void> {
  await openSwitcher(page);
  await page.getByRole('menuitem', { name: 'Find any being…' }).click();
}

/** A GM opens any being's board by searching for it. */
export async function browseBeing(page: Page, name: string): Promise<void> {
  await openFinder(page);
  const dialog = page.getByRole('dialog', { name: 'Find any being' });

  await dialog.getByLabel('Search beings').fill(name);
  await dialog.getByRole('option').getByRole('button', { name }).click();
}

/** A GM opens the board of what nobody owns. */
export async function showUnowned(page: Page): Promise<void> {
  await openSwitcher(page);
  await page.getByRole('menuitem', { name: 'Unowned things' }).click();
}

/** Opens the "Add an item" dialog from the board's bar. */
export async function openAdd(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Add an item' }).click();
}

/** The shell's library switcher, which says which library this is. */
export const libraryPicker = (page: Page) =>
  page.getByRole('combobox', { name: 'Library or repository' });

/** An action off a catalog row's "…" menu. */
export async function rowAction(row: Locator, name: string): Promise<void> {
  await row.getByRole('button', { name: 'Actions' }).click();
  await row.page().getByRole('menuitem', { name }).click();
}

/** The dialog that makes a catalog item, opened from the page's "New item". */
export async function openNewItem(page: Page): Promise<Locator> {
  await page.getByRole('button', { name: 'New item' }).click();

  return page.getByRole('dialog', { name: 'New item' });
}
