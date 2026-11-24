import AxeBuilder from '@axe-core/playwright';
import type { Page } from '@playwright/test';
import { browseBeing } from './support/board.ts';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';

// ADR 0524: the pages of Inventory, at a desktop and a phone width, in both themes, have no serious
// or critical accessibility violation, and nothing scrolls sideways at 390px.

const sizes = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'phone', width: 390, height: 844 },
] as const;
const schemes = ['light', 'dark'] as const;

async function serious(page: Page) {
  const result = await new AxeBuilder({ page }).disableRules(['region']).analyze();

  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({
      id: v.id,
      help: v.help,
      nodes: v.nodes.slice(0, 4).map((n) => ({ target: n.target, summary: n.failureSummary })),
    }));
}

for (const size of sizes) {
  for (const scheme of schemes) {
    test(`the pages are accessible at ${size.name} width in the ${scheme} theme`, async ({
      world,
      as,
    }) => {
      test.setTimeout(240_000);
      const { spellbook } = await packed(world, world.pia);
      const gm = await as(world.gm);

      await gm.emulateMedia({ colorScheme: scheme });
      await gm.setViewportSize({ width: size.width, height: size.height });

      const states: Array<[string, () => Promise<void>]> = [
        [
          'the board',
          async () => {
            await gm.goto(`/board/?tenant=${world.tenantId}`);
            await browseBeing(gm, 'Ashfang');
            await expect(gm.getByRole('region', { name: 'Equipped' })).toBeVisible();
          },
        ],
        [
          'the board, with the switcher open',
          async () => {
            await gm.locator('[data-switcher]').click();
            await expect(gm.getByRole('menuitem', { name: 'Unowned things' })).toBeVisible();
          },
        ],
        [
          'the catalog',
          async () => {
            await gm.goto(`/items/?tenant=${world.tenantId}`);
            await expect(gm.getByRole('list', { name: 'Catalog items' })).toBeVisible();
          },
        ],
        [
          'an item',
          async () => {
            await gm.goto(`/item/?tenant=${world.tenantId}&id=${spellbook}`);
            await expect(gm.getByRole('heading', { level: 1 })).toBeVisible();
          },
        ],
        [
          'unsorted',
          async () => {
            await gm.goto(`/unsorted/?tenant=${world.tenantId}`);
            await expect(gm.locator('main, #content').first()).toBeVisible();
          },
        ],
      ];

      for (const [name, show] of states) {
        await show();
        // Nothing scrolls sideways on a phone.
        if (size.name === 'phone') {
          const overflow = await gm.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          );

          expect(overflow, `${name} scrolls sideways`).toBeLessThanOrEqual(0);
        }

        // Colours ease between themes; what is measured is where they land.
        await gm.waitForTimeout(1500);
        expect(await serious(gm), name).toEqual([]);
      }
    });
  }
}
