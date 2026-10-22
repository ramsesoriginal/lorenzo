import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';
import { ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';
import { buildWorld } from './support/world.ts';

// ADR 0322: the golden-path pages, at a desktop and a phone width, in both themes, have no
// serious or critical accessibility violation, nothing scrolls sideways at 390px, and what is
// pressed is at least 44px tall there.

const sizes = [
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'phone', width: 390, height: 844 },
] as const;
const schemes = ['light', 'dark'] as const;

/** Everything pressed in the header and the page that is visible. */
const PRESSED =
  'header :is(button, a.btn, select, input:not([type=hidden], [type=checkbox], [type=radio], [type=file]), summary), main :is(button, a.btn, select, input:not([type=hidden], [type=checkbox], [type=radio], [type=file]), summary, label:has(> input[type=checkbox]), label:has(> input[type=radio]))';

async function gather(page: Page) {
  // Open every folding section, so what is inside is looked at too.
  await page.evaluate(() => {
    for (const details of document.querySelectorAll('details')) details.open = true;
  });
  // Opening a section may start a read (a note's recorded learning); let it finish.
  await page.waitForLoadState('networkidle');
}

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
    test(`golden-path pages are accessible at ${size.name} width in the ${scheme} theme`, async ({
      browser,
    }) => {
      // Five pages, each read twice by axe with its folding sections opened.
      test.setTimeout(180_000);
      const world = await buildWorld();
      const event = await ok(
        world.api.POST('/tenants/{tenant_id}/entities', {
          params: { path: { tenant_id: world.tenantId } },
          body: { name: 'The bell is rung', kinds: ['event'], parents: [] },
        }),
      );
      await ok(
        world.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
          params: { path: { tenant_id: world.tenantId, entity_id: event.id } },
          body: {
            title: 'What was heard',
            is_public: false,
            locale: 'en',
            type: 'note',
            content: 'The bell was heard across the harbour.',
          },
        }),
      );
      const token = await refreshTokenFor(world.subject);
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
      const calendar = `id=${world.calendarId}`;
      const tenant = `tenant=${world.tenantId}`;
      const pages = [
        {
          name: 'the calendar list',
          path: `/?${tenant}`,
          ready: async () =>
            expect(page.getByRole('link', { name: 'Isles calendar', exact: true })).toBeVisible(),
        },
        {
          name: 'a month',
          path: `/calendar/?${tenant}&${calendar}&year=3286&segment=segment-6&day=16`,
          ready: async () => {
            await expect(page.locator('.day')).toHaveCount(27);
            await expect(
              page.locator('.day-content').filter({ hasText: 'Loading notes' }),
            ).toHaveCount(0);
            await expect(
              page.locator('aside').getByText('A lantern was lit by the harbour.'),
            ).toBeVisible();
          },
        },
        {
          name: 'the whole year',
          path: `/calendar/?${tenant}&${calendar}&year=3286&view=year`,
          ready: async () => {
            await expect(page.locator('.year-segment .day').first()).toBeVisible();
            await expect(
              page.locator('.day-content').filter({ hasText: 'Loading notes' }),
            ).toHaveCount(0);
          },
        },
        {
          name: 'an entry',
          path: `/entry/?${tenant}&id=${event.id}`,
          ready: async () => {
            await expect(page.getByRole('heading', { name: event.name, level: 1 })).toBeVisible();
            await expect(page.getByText('The bell was heard across the harbour.')).toBeVisible();
            await expect(page.locator('[data-learning]')).toBeVisible();
          },
        },
        {
          name: 'the Events page',
          path: `/events/?${tenant}`,
          ready: async () => {
            await expect(page.getByRole('link', { name: event.name, exact: true })).toBeVisible();
            await expect(page.getByRole('status')).toHaveText(/Events?\./);
          },
        },
      ];
      const problems: object[] = [];
      for (const target of pages) {
        await page.goto(target.path);
        await target.ready();
        await expect(page.locator('html')).toHaveAttribute('data-theme', scheme);
        await page.screenshot({
          path: test
            .info()
            .outputPath(`${target.name.replaceAll(' ', '-')}-${size.name}-${scheme}-rest.png`),
          fullPage: true,
        });
        await gather(page);
        await page.screenshot({
          path: test
            .info()
            .outputPath(`${target.name.replaceAll(' ', '-')}-${size.name}-${scheme}.png`),
          fullPage: true,
        });
        problems.push(...(await serious(page)).map((v) => ({ page: target.name, ...v })));
        if (size.name === 'phone') {
          if (!(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)))
            problems.push({ page: target.name, id: 'scrolls sideways at 390px' });
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
