import { randomUUID } from 'node:crypto';
import { ok } from '../../../beings/tests/e2e/support/api.ts';
import { expect, test } from '../../../beings/tests/e2e/support/fixtures.ts';

// ADR 0387: the compare grid reads its columns in bulk, a page of entries a request, and reads an
// entry in full only when it is changed.
test('the grid reads its values a page at a time and an entry in full only when it is changed', async ({
  world,
  as,
}) => {
  const api = world.gm.api;
  const repository = await ok(
    api.POST('/tenants', { body: { name: `Grid ${randomUUID()}`, kind: 'repository' } }),
  );
  const path = { tenant_id: repository.id };
  const group = await ok(
    api.POST('/tenants/{tenant_id}/stat-groups', {
      params: { path },
      body: { name: 'Combat', priority: 0, mandatory: false },
    }),
  );
  const stat = async (name: string) =>
    ok(
      api.POST('/tenants/{tenant_id}/stat-definitions', {
        params: { path },
        body: {
          name,
          stat_group_id: group.id,
          value_type: 'int',
          adjustable_in_play: false,
          pin: false,
          signed: false,
        },
      }),
    );
  const strength = await stat('Strength');
  const bonus = await stat('Bonus');
  const entry = async (name: string, parents: string[]) =>
    ok(
      api.POST('/tenants/{tenant_id}/entities', {
        params: { path },
        body: { name, kinds: ['item'], parents },
      }),
    );
  const setStat = (entryId: string, definitionId: string, value: number) =>
    ok(
      api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
        params: { path: { ...path, entity_id: entryId, stat_definition_id: definitionId } },
        body: { value, acquire_group: true },
      }),
    );
  const fighter = await entry('Fighter', []);
  const weak = await entry('Weak', [fighter.id]);
  const strong = await entry('Strong', [fighter.id]);
  await setStat(fighter.id, strength.id, 10);
  await setStat(strong.id, strength.id, 18);
  // A formula held by Fighter: the bonus is the strength, scaled, so it is worked out for each.
  await ok(
    api.PUT('/tenants/{tenant_id}/entities/{entity_id}/computed-stats/{stat_definition_id}', {
      params: { path: { ...path, entity_id: fighter.id, stat_definition_id: bonus.id } },
      body: {
        kind: 'linear',
        source_stat_definition_id: strength.id,
        multiplier: 0.5,
        offset: 0,
        round_mode: 'floor',
      },
    }),
  );

  const page = await as(world.gm);
  await page.setViewportSize({ width: 1440, height: 900 });
  const details: string[] = [];
  const bulk: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (request.method() !== 'GET') return;
    if (url.pathname.endsWith('/entities/effective-stats')) bulk.push(url.search);
    else if (/\/entities\/[0-9a-f-]{36}$/.test(url.pathname)) details.push(url.pathname);
  });
  await page.goto('/');
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('Open Compare');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill('Float Compare');
  await page.keyboard.press('Enter');
  const grid = page.locator('.pane-grid');
  const rowOf = (name: string) =>
    grid
      .locator('table.grid tbody tr')
      .filter({ has: page.getByRole('button', { name, exact: true }) });

  // Which stat column is which: the headers, less the ones that are not stat cells.
  await expect(rowOf('Fighter')).toBeVisible();
  const headers = await grid.locator('table.grid thead th').allTextContents();
  const cells = await rowOf('Fighter').locator('td').count();
  const at = (name: string) =>
    headers.findIndex((h) => h.includes(name)) - (headers.length - cells);
  const [S, B] = [at('Strength'), at('Bonus')];
  const cell = (row: string, column: number) => rowOf(row).locator('td').nth(column);

  // Own, inherited and worked-out values, read without opening a single entry.
  await expect(cell('Fighter', S)).toHaveText('10');
  await expect(cell('Strong', S)).toHaveText('18');
  await expect(cell('Weak', S)).toContainText('10');
  await expect(cell('Weak', B)).toContainText('5');
  await expect(cell('Strong', B)).toContainText('9');
  expect(bulk.length).toBeGreaterThan(0);
  expect(bulk[0]).toContain(`stat_definition_id=${strength.id}`);
  expect(details.filter((p) => !p.endsWith(`/${fighter.id}`))).toEqual([]);

  // Typing in a cell reads that entry in full, then writes it.
  await cell('Weak', S).click();
  await page.keyboard.type('12');
  await page.keyboard.press('Enter');
  await expect
    .poll(
      async () =>
        (
          await ok(
            api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: { ...path, entity_id: weak.id } },
            }),
          )
        ).stats.find((s) => s.name === 'Strength')?.value,
    )
    .toBe(12);
  await expect(cell('Weak', S)).toHaveText('12');
});
