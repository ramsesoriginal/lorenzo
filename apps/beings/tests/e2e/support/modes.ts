import { expect, type Page } from '@playwright/test';

/** Switches the sheet to a mode, through the switch in its header. */
export async function enterMode(page: Page, mode: 'Read' | 'Play' | 'Edit'): Promise<void> {
  await page
    .locator('[data-sheet-head] [data-mode-switch]')
    .getByText(mode, { exact: true })
    .click();
  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', mode.toLowerCase());
}
