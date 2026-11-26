import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';
import { ok } from './support/api.ts';
import { signedIn, standing, world } from './support/world.ts';

/** Every control a thumb presses is at least 44px tall on a phone, and nothing scrolls sideways. */
async function fitsAPhone(page: Page): Promise<number> {
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(sideways).toBeLessThanOrEqual(0);
  const { small, seen } = await page.evaluate(() => {
    const out: string[] = [];
    let seen = 0;
    for (const node of document.querySelectorAll<HTMLElement>(
      'main button, main select, main input:not([type="checkbox"]):not([type="radio"])',
    )) {
      const box = node.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      // The matrix grid's own cells are a grid, not controls laid out for a thumb.
      if (node.closest('.matrix')) continue;
      seen += 1;
      if (box.height < 43.5)
        out.push(
          `${node.tagName} ${node.textContent?.trim().slice(0, 30)} ${Math.round(box.height)}`,
        );
    }
    return { small: out, seen };
  });
  expect(small).toEqual([]);
  return seen;
}

async function everything() {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const mara = await w.person('Mara Quill');
  const wren = await w.person('Wren Ashdown');
  const tie = await w.tie('Mara is the parent of Wren', mara.id, wren.id, true);
  const made = await ok(
    w.gm.POST('/tenants/{tenant_id}/social-webs', {
      params: { path: w.path },
      body: { name: 'The court', is_public: true, layout: 'circle', layout_seed: 1 },
    }),
  );
  const read = await w.gm.GET('/tenants/{tenant_id}/social-webs/{web_id}', {
    params: { path: { ...w.path, web_id: made.id } },
  });
  await ok(
    w.gm.POST('/tenants/{tenant_id}/social-webs/{web_id}/members/bulk', {
      params: { path: { ...w.path, web_id: made.id } },
      headers: { 'If-Match': read.response.headers.get('etag') ?? '' },
      body: { set: [mara.id, wren.id].map((entry_id) => ({ entry_id })) },
    }),
  );
  const t = `tenant=${w.tenant.id}`;
  const pages = [
    ['webs', `/webs/?${t}`],
    ['web graph', `/web/?${t}&id=${made.id}`],
    ['web list', `/web/?${t}&id=${made.id}&view=list`],
    ['web matrix', `/web/?${t}&id=${made.id}&view=matrix`],
    ['relationships', `/relationships/?${t}`],
    ['a relationship', `/relationship/?${t}&id=${tie.id}`],
    ['types', `/types/?${t}`],
    ['problems', `/problems/?${t}`],
    ['an entry', `/entry/?${t}&id=${mara.id}`],
  ] as const;
  return { w, pages, honor };
}

for (const theme of ['light', 'dark'] as const) {
  test(`every page has no axe violations in ${theme}, with its dialogs and panel open`, async ({
    browser,
  }) => {
    const { w, pages } = await everything();
    const page = await signedIn(browser, w.subject, theme);
    for (const [name, url] of pages) {
      await page.goto(url);
      await expect(page.getByRole('main')).toBeVisible();
      await page.waitForTimeout(600);
      const found = (await new AxeBuilder({ page }).analyze()).violations;
      expect(found.map((v) => `${name}: ${v.id}`)).toEqual([]);
    }
    // States that are not a page of their own: the panel, a dialog.
    await page.goto(pages[1][1]);
    await page.getByRole('button', { name: 'Notes', exact: true }).click();
    expect((await new AxeBuilder({ page }).analyze()).violations.map((v) => v.id)).toEqual([]);
    await page.getByRole('button', { name: 'Members' }).click();
    await expect(page.getByRole('group', { name: 'Members' })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations.map((v) => v.id)).toEqual([]);
    await page.getByRole('button', { name: 'Close', exact: true }).click();
    // The date lens' Event chooser, with its list and the shared time filter.
    await page.getByRole('button', { name: 'As of an Event' }).click();
    await expect(page.getByRole('group', { name: 'As of this Event' })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations.map((v) => v.id)).toEqual([]);
    await page.getByRole('button', { name: 'Connect' }).click();
    await expect(page.getByRole('form', { name: 'Connect two entries' })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations.map((v) => v.id)).toEqual([]);
  });
}

test('on a phone every page fits the width and its controls are tall enough to press', async ({
  browser,
}) => {
  const { w, pages } = await everything();
  const page = await signedIn(browser, w.subject);
  await page.setViewportSize({ width: 390, height: 800 });
  let checked = 0;
  for (const [, url] of pages) {
    await page.goto(url);
    await expect(page.getByRole('main')).toBeVisible();
    await page.waitForTimeout(600);
    checked += await fitsAPhone(page);
  }
  // The check looks at something: the pages hold controls, and it measured them.
  expect(checked).toBeGreaterThan(20);
});

test('on a tablet the web keeps its bar and panel and nothing scrolls sideways', async ({
  browser,
}) => {
  const { w, pages } = await everything();
  const page = await signedIn(browser, w.subject);
  await page.setViewportSize({ width: 820, height: 1100 });
  for (const [, url] of pages) {
    await page.goto(url);
    await expect(page.getByRole('main')).toBeVisible();
    await page.waitForTimeout(400);
    const sideways = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(sideways).toBeLessThanOrEqual(0);
  }
  await page.goto(pages[1][1]);
  await expect(page.getByRole('button', { name: 'Focus' })).toBeVisible();
});
