import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';
import { ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';
import { buildWorld } from './support/world.ts';

// ADR 0524: the pages of Beings, at a desktop and a phone width, in both themes, have no serious
// or critical accessibility violation, nothing scrolls sideways at 390px, and what is pressed is at
// least 44px tall there.

const sizes = [
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'phone', width: 390, height: 844 },
] as const;
const schemes = ['light', 'dark'] as const;

/** Everything pressed in the header and the page that is visible. */
const PRESSED =
  'header :is(button, a.btn, select, input:not([type=hidden], [type=checkbox], [type=radio], [type=file]), summary), main :is(button, a.btn, select, input:not([type=hidden], [type=checkbox], [type=radio], [type=file]), summary, label:has(> input[type=checkbox]), label:has(> input[type=radio]))';

async function serious(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({
      id: v.id,
      impact: v.impact,
      help: v.help,
      nodes: v.nodes.slice(0, 4).map((n) => ({ target: n.target, summary: n.failureSummary })),
    }));
}

for (const size of sizes) {
  for (const scheme of schemes) {
    test(`the pages are accessible at ${size.name} width in the ${scheme} theme`, async ({
      browser,
    }) => {
      test.setTimeout(240_000);
      const world = await buildWorld();
      const being = world.pia.character.entity_id;
      const hp = await world.defineStat('vitals', 'hit_points', 'int', {
        adjustable_in_play: true,
        pin: true,
      });
      const body = await world.defineStat('vitals', 'body', 'int');
      await world.defineStat('tags', 'prone', 'bool', { adjustable_in_play: true });
      await world.setStat(being, hp.id, 14);
      await world.setStat(being, body.id, 3);
      await world.describe(being, 'A knight of the **Ash Road**.');
      await world.note(being, 'Backstory', 'Raised by wolves.', true);
      const fact = await ok(
        world.gm.api.POST('/tenants/{tenant_id}/entities', {
          params: { path: { tenant_id: world.tenantId } },
          body: { name: 'The tether', slug: 'tether', kinds: ['fact'], parents: [] },
        }),
      );
      await world.note(being, 'A reference', 'See [the tether](tether).', true);

      const token = await refreshTokenFor(world.gm.subject);
      const context = await browser.newContext({
        colorScheme: scheme,
        viewport: { width: size.width, height: size.height },
        storageState: {
          cookies: [],
          origins: [
            { origin: SITE_URL, localStorage: [{ name: REFRESH_TOKEN_KEY, value: token }] },
          ],
        },
      });
      const page = await context.newPage();
      const tenant = `tenant=${world.tenantId}`;
      const pages = [
        {
          name: 'the libraries',
          path: '/',
          ready: async () => expect(page.getByRole('link').first()).toBeVisible(),
        },
        {
          name: 'the list as rows',
          path: `/beings/?${tenant}`,
          ready: async () => expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible(),
        },
        {
          name: 'the list as cards',
          path: `/beings/?${tenant}`,
          ready: async () => {
            await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();
            await page.getByRole('radiogroup', { name: 'View' }).getByText('Cards').click();
            await expect(page.locator('.card-number').first()).toBeVisible();
          },
        },
        {
          name: 'the list side by side',
          path: `/beings/?${tenant}`,
          ready: async () => {
            await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();
            await page.getByRole('radiogroup', { name: 'View' }).getByText('Side by side').click();
            await expect(page.getByRole('rowheader', { name: 'Body' })).toBeVisible();
          },
        },
        {
          name: 'a being in Read',
          path: `/being/?${tenant}&id=${being}`,
          ready: async () => {
            await expect(page.getByRole('heading', { name: 'Ashfang', level: 1 })).toBeVisible();
            await expect(page.getByRole('heading', { name: 'Backstory' })).toBeVisible();
            await expect(page.getByRole('button', { name: 'More for this being' })).toBeVisible();
          },
        },
        {
          name: 'a being with its details open',
          path: `/being/?${tenant}&id=${being}`,
          ready: async () => {
            await page.getByRole('button', { name: 'More for this being' }).click();
            await page.getByRole('menuitem', { name: 'Edit details' }).click();
            await expect(page.locator('[data-name-edit]')).toBeVisible();
            await page.getByRole('button', { name: 'Edit Body', exact: true }).click();
          },
        },
        {
          name: 'a being in Play',
          path: `/being/?${tenant}&id=${being}`,
          ready: async () => {
            await expect(page.getByRole('button', { name: 'More for this being' })).toBeVisible();
            await page.locator('[data-band] [data-mode-switch]').getByText('Play').click();
            await expect(
              page.locator('[data-stat="hit_points"]').getByRole('button', { name: /Lower/ }),
            ).toBeVisible();
          },
        },
        {
          name: 'where a Fact appears',
          path: `/appears/?${tenant}&id=${fact.id}`,
          ready: async () => {
            await expect(
              page.getByRole('heading', { name: 'Where The tether appears' }),
            ).toBeVisible();
            await expect(page.getByRole('link', { name: 'Ashfang' })).toBeVisible();
          },
        },
      ];
      const problems: object[] = [];

      for (const target of pages) {
        await page.goto(target.path);
        await target.ready();
        // A page may still be settling (the home goes on to the one library); axe looks at the last.
        await page.waitForLoadState('networkidle');
        await expect(page.locator('html')).toHaveAttribute('data-theme', scheme);
        await page.screenshot({
          path: test
            .info()
            .outputPath(`${target.name.replaceAll(' ', '-')}-${size.name}-${scheme}.png`),
          fullPage: true,
        });
        problems.push(...(await serious(page)).map((v) => ({ page: target.name, ...v })));

        if (size.name === 'phone') {
          if (!(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))) {
            problems.push({ page: target.name, id: 'scrolls sideways at 390px' });
          }

          const small = await page.evaluate((selector) => {
            const visible = (node: Element) =>
              node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden';

            return [...document.querySelectorAll(selector)]
              .filter(visible)
              .map((node) => ({
                node: `${node.tagName.toLowerCase()}.${node.className?.toString().slice(0, 40)} "${(node.textContent ?? '').trim().slice(0, 30)}"`,
                height: Math.round(node.getBoundingClientRect().height * 10) / 10,
              }))
              .filter((entry) => entry.height < 43.5);
          }, PRESSED);

          if (small.length) problems.push({ page: target.name, id: 'controls under 44px', small });
        }
      }

      await context.close();
      expect(problems).toEqual([]);
    });
  }
}
