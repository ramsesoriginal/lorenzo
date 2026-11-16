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

/**
 * The part of the sheet that is free: once the panel beside it has stopped moving it, and to the right
 * of the card that floats over its left edge, so a click at a fraction of it is a click on the sheet.
 */
export async function stageBox(page: Page) {
  const stage = page.locator('.map-stage');
  let last = await stage.boundingBox();
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(100);
    const now = await stage.boundingBox();
    if (now && last && now.width === last.width && now.x === last.x && now.height === last.height) {
      last = now;
      break;
    }
    last = now;
  }
  if (!last) return last;
  const left = await page.locator('.map-float--left').first().boundingBox();
  const edge = left ? Math.max(0, left.x + left.width + 16 - last.x) : 0;
  return { x: last.x + edge, y: last.y, width: last.width - edge, height: last.height };
}
