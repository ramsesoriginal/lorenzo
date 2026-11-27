import { expect, test } from './support/fixtures.ts';

// A person's appearance follows them through their account (ADR 0532).
test('the account’s appearance is applied once signed in, and a change is sent back', async ({
  world,
  as,
}) => {
  await world.gm.api.PUT('/me/preferences', { body: { theme: 'dark', density: 'compact' } });

  const page = await as(world.gm);

  await page.goto(`/beings/?tenant=${world.tenantId}`);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('html')).toHaveAttribute('data-density', 'compact');

  await page.getByRole('button', { name: /account menu/ }).click();
  await page.getByRole('menuitem', { name: /Appearance/ }).click();
  await page
    .getByRole('radiogroup', { name: 'Density of lists and tables' })
    .getByRole('radio', { name: 'Dense' })
    .click();

  await expect
    .poll(async () => (await world.gm.api.GET('/me/preferences')).data?.density)
    .toBe('dense');
  expect((await world.gm.api.GET('/me/preferences')).data?.theme).toBe('dark');
});
