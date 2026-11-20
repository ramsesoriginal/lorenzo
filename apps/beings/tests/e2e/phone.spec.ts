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
  await expect(page.locator('[data-band] [data-mode-switch]')).toBeVisible();
  expect(await overflows()).toBe(false);
});

test('the cards and the side-by-side table scroll inside themselves, not the page', async ({
  world,
  as,
}) => {
  await world.npc('Goblin Chief');
  await world.npc('Goblin Archer');
  const page = await as(world.gm);
  const overflows = () =>
    page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );

  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();
  const view = page.getByRole('radiogroup', { name: 'View' });
  await view.getByText('Cards').click();
  await expect(page.locator('[data-list] .being-cards')).toBeVisible();
  expect(await overflows()).toBe(false);

  await view.getByText('Side by side').click();
  await expect(page.getByRole('region', { name: 'Beings side by side' })).toBeVisible();
  expect(await overflows()).toBe(false);
});
