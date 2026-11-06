import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { ok } from './support/api.ts';
import { signedIn, standing, world } from './support/world.ts';

async function courtOf(w: Awaited<ReturnType<typeof world>>, members: string[]) {
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
      body: { set: members.map((entry_id) => ({ entry_id })) },
    }),
  );
  return made;
}

test('a GM sets a standing in an empty cell, and a relationship is made, restricted, with it', async ({
  browser,
}) => {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const mara = await w.entry('Mara Quill');
  const wren = await w.entry('Wren Ashdown');
  const dren = await w.entry('Dren Holloway');
  const court = await courtOf(w, [mara.id, wren.id, dren.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/matrix/?tenant=${w.tenant.id}&id=${court.id}`);
  const grid = page.getByRole('grid', { name: 'Relationship matrix' });
  await expect(grid).toBeVisible();
  await expect(grid.getByRole('columnheader', { name: 'Wren Ashdown' })).toBeVisible();
  await page.getByRole('combobox', { name: /^Standing/ }).selectOption(honor.id);

  // The keyboard path: focus a cell, type a number, Enter commits and moves down.
  const cell = grid.getByRole('gridcell', { name: /^Mara Quill to Wren Ashdown, none/ });
  await cell.focus();
  await page.keyboard.type('7');
  await page.keyboard.press('Enter');
  await expect(
    grid.getByRole('gridcell', { name: /^Mara Quill to Wren Ashdown, 7, not saved/ }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save changes (1)' })).toBeEnabled();

  // A value outside the scale is refused where it is typed, and nothing is lost.
  const other = grid.getByRole('gridcell', { name: /^Wren Ashdown to Dren Holloway, none/ });
  await other.focus();
  await page.keyboard.type('11');
  await page.keyboard.press('Enter');
  await expect(page.getByText('11 is above the scale (up to 10).')).toBeVisible();
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'Save changes (1)' }).click();
  await expect(page.getByText('Saved 1 change.')).toBeVisible();
  await expect(
    grid.getByRole('gridcell', { name: /^Mara Quill to Wren Ashdown, 7/ }),
  ).toBeVisible();

  // Made restricted, named for its ends, and holding the value.
  const list = await ok(
    w.gm.GET('/tenants/{tenant_id}/relationships', { params: { path: w.path } }),
  );
  expect(list.items).toHaveLength(1);
  expect(list.items[0]?.is_public).toBe(false);
  expect(list.items[0]?.name).toBe('Mara Quill - Wren Ashdown');
});

test('a player reads the matrix and may not change it; a hidden end leaves an empty cell', async ({
  browser,
}) => {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const mara = await w.entry('Mara Quill');
  const wren = await w.entry('Wren Ashdown');
  const vault = await w.entry('The sealed vault', false);
  const open = await w.tie('Open bond', mara.id, wren.id, true);
  await w.tie('Cut bond', mara.id, vault.id, true);
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: { path: { ...w.path, entity_id: open.id, stat_definition_id: honor.id } },
      body: { value: 4, acquire_group: true },
    }),
  );
  const court = await courtOf(w, [mara.id, wren.id, vault.id]);
  const page = await signedIn(browser, w.playerSubject);
  await page.goto(`/matrix/?tenant=${w.tenant.id}&id=${court.id}`);
  const grid = page.getByRole('grid', { name: 'Relationship matrix' });
  await expect(grid).toBeVisible();
  await page.getByRole('combobox', { name: /^Standing/ }).selectOption(honor.id);
  await expect(
    grid.getByRole('gridcell', { name: /^Mara Quill to Wren Ashdown, 4/ }),
  ).toBeVisible();
  await expect(grid.getByText('sealed vault')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Save changes/ })).toHaveCount(0);
  await grid.getByRole('gridcell', { name: /^Mara Quill to Wren Ashdown, 4/ }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('You may read these, not change them.')).toBeVisible();
});

test('two relationships for one cell are shown as a conflict', async ({ browser }) => {
  const w = await world();
  await standing(w, 'Honor');
  const mara = await w.entry('Mara Quill');
  const wren = await w.entry('Wren Ashdown');
  await w.tie('First', mara.id, wren.id, true);
  await w.tie('Second', mara.id, wren.id, true);
  const court = await courtOf(w, [mara.id, wren.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/matrix/?tenant=${w.tenant.id}&id=${court.id}`);
  const cell = page.getByRole('gridcell', { name: /2 relationships, a conflict/ }).first();
  await expect(cell).toBeVisible();
  await expect(cell).toContainText('2 here');
});

for (const theme of ['light', 'dark'] as const) {
  test(`the matrix has no axe violations in ${theme}`, async ({ browser }) => {
    const w = await world();
    const honor = await standing(w, 'Honor');
    const mara = await w.entry('Mara Quill');
    const wren = await w.entry('Wren Ashdown');
    const tie = await w.tie('Bond', mara.id, wren.id, true);
    await ok(
      w.gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
        params: { path: { ...w.path, entity_id: tie.id, stat_definition_id: honor.id } },
        body: { value: 2, acquire_group: true },
      }),
    );
    const court = await courtOf(w, [mara.id, wren.id]);
    const page = await signedIn(browser, w.subject, theme);
    await page.goto(`/matrix/?tenant=${w.tenant.id}&id=${court.id}`);
    await expect(page.getByRole('grid', { name: 'Relationship matrix' })).toBeVisible();
    await page.getByRole('combobox', { name: /^Standing/ }).selectOption(honor.id);
    await expect(
      page.getByRole('gridcell', { name: /^Mara Quill to Wren Ashdown, 2/ }),
    ).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });
}

test('on a phone one entry has its standings as a list with the same save', async ({ browser }) => {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const mara = await w.entry('Mara Quill');
  const wren = await w.entry('Wren Ashdown');
  const court = await courtOf(w, [mara.id, wren.id]);
  const page = await signedIn(browser, w.subject);
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto(`/matrix/?tenant=${w.tenant.id}&id=${court.id}`);
  await expect(page.getByText('The matrix is for a tablet or a desktop.')).toBeVisible();
  await expect(page.getByRole('grid')).toHaveCount(0);
  await page.getByRole('combobox', { name: /^Standing/ }).selectOption(honor.id);
  const input = page.getByLabel('Mara Quill to Wren Ashdown: Honor');
  await input.fill('3');
  await input.press('Tab');
  await page.getByRole('button', { name: 'Save changes (1)' }).click();
  await expect(page.getByText('Saved 1 change.')).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
