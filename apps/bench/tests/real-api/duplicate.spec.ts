import { randomUUID } from 'node:crypto';
import { ok } from '../../../beings/tests/e2e/support/api.ts';
import { expect, test } from '../../../beings/tests/e2e/support/fixtures.ts';

// ADR 0388: Duplicate makes a copy as commands (kinds, parents, own stats, description, notes) and
// then the formulas the entry holds, and New under this makes an entry whose parent is the open one.
test('an entry is duplicated, formula included, and a new entry is made under it', async ({
  world,
  as,
}) => {
  const api = world.gm.api;
  const repository = await ok(
    api.POST('/tenants', { body: { name: `Forge ${randomUUID()}`, kind: 'repository' } }),
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
  const armor = await stat('Armor');
  const damage = await stat('Damage');
  const weapon = await ok(
    api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Weapon', kinds: ['item'], parents: [] },
    }),
  );
  const sword = await ok(
    api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Sword', kinds: ['item'], parents: [weapon.id] },
    }),
  );
  await ok(
    api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: { path: { ...path, entity_id: sword.id, stat_definition_id: armor.id } },
      body: { value: 3, acquire_group: true },
    }),
  );
  await ok(
    api.PUT('/tenants/{tenant_id}/entities/{entity_id}/computed-stats/{stat_definition_id}', {
      params: { path: { ...path, entity_id: sword.id, stat_definition_id: damage.id } },
      body: {
        kind: 'linear',
        source_stat_definition_id: armor.id,
        multiplier: 2,
        offset: 1,
        round_mode: 'floor',
      },
    }),
  );
  await ok(
    api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { ...path, entity_id: sword.id } },
      body: {
        type: 'description',
        title: 'Description',
        content: 'A keen blade.',
        is_public: true,
        locale: 'en-US',
      },
    }),
  );
  await ok(
    api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { ...path, entity_id: sword.id } },
      body: {
        type: 'note',
        title: 'Note',
        content: 'The notch is a secret.',
        is_public: false,
        locale: 'en-US',
      },
    }),
  );

  const page = await as(world.gm);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.getByRole('button', { name: 'A to Z', exact: true }).click();
  await page.locator(`[data-entry="${sword.id}"]`).first().click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Sword');
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');

  await page.getByRole('button', { name: 'Duplicate', exact: true }).click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Copy of Sword');
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');

  const listed = await ok(
    api.GET('/tenants/{tenant_id}/entities', { params: { path, query: { q: 'Copy of Sword' } } }),
  );
  const copy = listed.items[0];
  if (!copy) throw new Error('The copy was not made.');
  expect(copy.parent_ids).toEqual([weapon.id]);
  expect(copy.kinds).toEqual(['item']);
  // The formula arrives once the copy is on the server, so wait for it.
  await expect
    .poll(async () => {
      const formulas = await ok(
        api.GET('/tenants/{tenant_id}/entities/{entity_id}/computed-stats', {
          params: { path: { ...path, entity_id: copy.id } },
        }),
      );
      return formulas.map((f) => f.stat_definition_id);
    })
    .toEqual([damage.id]);
  const made = await ok(
    api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { ...path, entity_id: copy.id } },
    }),
  );
  const own = made.stats.filter((s) => s.own).map((s) => [s.name, s.value]);
  expect(own).toContainEqual(['Armor', 3]);
  expect(own.map((s) => s[0])).toContain('Damage'); // the formula, worked out
  expect(made.information.map((i) => i.type).sort()).toEqual(['description', 'note']);
  expect(made.information.find((i) => i.type === 'note')?.is_public).toBe(false);
  // Not copied: the link name (the original has none here; the copy's is made from its own name).
  const link = await ok(
    api.GET('/tenants/{tenant_id}/entities/resolve', {
      params: { path, query: { slug: ['sword'] } },
    }),
  );
  expect(link.map((l) => l.entity_id)).not.toContain(copy.id);

  // New under this: the form opens with the open entry as the parent.
  await page.getByRole('button', { name: 'New under this' }).click();
  await page.locator('.new-entry').getByLabel('Name of the new entry').fill('Rapier');
  await page.locator('.new-entry').getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Rapier');
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');
  const rapier = await ok(
    api.GET('/tenants/{tenant_id}/entities', { params: { path, query: { q: 'Rapier' } } }),
  );
  expect(rapier.items[0]?.parent_ids).toEqual([copy.id]);
});
