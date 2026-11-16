import { expect, test } from '@playwright/test';
import { contrast, resolve, setTheme, token } from './support';

// WCAG 1.4.11 and 1.4.3: the edge of a control is at least 3:1 against its surface, and tertiary text
// is at least 4.5:1 on paper and on a selected surface, in both themes.
for (const theme of ['light', 'dark'] as const) {
  test.describe(theme, () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/preview/forms.html');
      await setTheme(page, theme);
    });

    test('the edge of a field, a segmented control and a switch is at least 3:1 against the surface', async ({ page }) => {
      const surface = await resolve(page, '.text-input', 'background-color');
      expect(contrast(await resolve(page, '.text-input', 'border-top-color'), surface)).toBeGreaterThanOrEqual(3);
      expect(contrast(await resolve(page, '.segmented-control', 'border-top-color'), surface)).toBeGreaterThanOrEqual(3);
      // The track of a switch that is off.
      await page.locator('.switch input').first().uncheck({ force: true });
      await page.waitForTimeout(300);
      expect(contrast(await resolve(page, '.switch-track', 'background-color'), surface)).toBeGreaterThanOrEqual(3);
    });

    test('tertiary text is at least 4.5:1 on paper and on a selected surface', async ({ page }) => {
      const tertiary = await token(page, '--text-tertiary');
      expect(contrast(tertiary, await token(page, '--surface-default'))).toBeGreaterThanOrEqual(4.5);
      expect(contrast(tertiary, await token(page, '--surface-selected'))).toBeGreaterThanOrEqual(4.5);
    });
  });
}

test('the type roles and motion tokens exist', async ({ page }) => {
  await page.goto('/preview/forms.html');
  const values = await page.evaluate(() => {
    const cs = getComputedStyle(document.documentElement);
    const names = ['--fs-heading', '--fs-sub', '--fs-body', '--fs-ui', '--fs-meta', '--fs-micro', '--fs-code', '--dur-fast', '--dur-med', '--dur-slow', '--ease', '--space-2h', '--border-control'];
    return Object.fromEntries(names.map((n) => [n, cs.getPropertyValue(n).trim()]));
  });
  for (const [name, value] of Object.entries(values)) expect(value, name).not.toBe('');
  expect(values['--fs-micro']).toBe('0.75rem'); // nothing below 12px
  expect(values['--dur-med']).toBe('220ms');
});

test('a control is 36px tall, 44px on a phone', async ({ page }) => {
  await page.goto('/preview/forms.html');
  expect((await page.locator('.btn').first().boundingBox())?.height).toBeCloseTo(36, 0);
  await page.setViewportSize({ width: 430, height: 900 });
  expect((await page.locator('.btn').first().boundingBox())?.height).toBeGreaterThanOrEqual(44);
});
