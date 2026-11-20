import { expect, type Page } from '@playwright/test';

/** Switches the page to a mode, through the switch in its band. */
export async function enterMode(page: Page, mode: 'Read' | 'Play'): Promise<void> {
  await page.locator('[data-band] [data-mode-switch]').getByText(mode, { exact: true }).click();
  await expect(page.locator('[data-being-page]')).toHaveAttribute('data-mode', mode.toLowerCase());
}

/** Opens the forms of the being's details (name, picture, link name, tags) in the header. */
export async function editDetails(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Edit details' }).click();
}
