import { expect, type Page } from '@playwright/test';

/** Switches the page to a mode, through the switch in its band. */
export async function enterMode(page: Page, mode: 'Read' | 'Play'): Promise<void> {
  await page.locator('[data-band] [data-mode-switch]').getByText(mode, { exact: true }).click();
  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', mode.toLowerCase());
}

/** The page's "⋯" menu, which is there for whoever may change the being. */
export const pageMenu = (page: Page) => page.getByRole('button', { name: 'More for this being' });

/** Chooses an item of the page's menu. */
export async function chooseFromMenu(page: Page, item: string): Promise<void> {
  await pageMenu(page).click();
  await page.getByRole('menuitem', { name: item }).click();
}

/** Opens the forms of the being's details (name, picture, link name, tags). */
export async function editDetails(page: Page): Promise<void> {
  await chooseFromMenu(page, 'Edit details');
}

/** The layout switch in view: the sheet's, or the datasheet's. */
export const layoutSwitch = (page: Page) => page.locator('[data-layout-switch]:visible');
