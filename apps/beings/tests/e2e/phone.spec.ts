import { expect, test } from './support/fixtures.ts';

// A phone: one column, nothing wider than the screen (ADR 0270).
test.use({ viewport: { width: 375, height: 700 } });

test('the list and a being’s page fit a phone without sideways scrolling', async ({
  world,
  as,
}) => {
  await world.describe(world.pia.character.entity_id, 'A knight.');
  await world.note(world.pia.character.entity_id, 'Backstory', 'Raised by wolves.', true);
  const page = await as(world.gm);
  const overflows = () =>
    page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );

  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();
  expect(await overflows()).toBe(false);

  await page.getByRole('link', { name: 'Ashfang' }).click();
  await expect(page.getByRole('heading', { name: 'Backstory' })).toBeVisible();
  await expect(page.locator('[data-sheet-head] [data-mode-switch]')).toBeVisible();
  expect(await overflows()).toBe(false);
});
