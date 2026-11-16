import type { Page } from '@playwright/test';

// The Map page (MP3): its controls float over the Map, and a panel slides over for the selected
// mark, the places and the settings. These open what a test needs, and leave it open.

/** A floating control that opens a small panel: Layers, Look, Legend or Projection. */
export async function openControl(page: Page, name: 'Layers' | 'Look' | 'Legend' | 'Projection') {
  const trigger = page.getByRole('button', { name, exact: true });
  if ((await trigger.getAttribute('aria-expanded')) !== 'true') await trigger.click();
}

/** The slide-over panel, on one of its tabs. */
export async function openPanel(page: Page, tab: 'Selected' | 'Places' | 'History' | 'Settings') {
  const panel = page.locator('.map-slideover');
  if (!(await panel.isVisible())) {
    // Places opens it on the tab it names; the others through the Places button, then the tab.
    await page.getByRole('button', { name: 'Places', exact: true }).click();
  }
  await page.getByRole('tab', { name: tab, exact: true }).click();
}
