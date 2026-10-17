import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';

test('facts-about and text links conceal an anchor until its outer audience is explicit', async ({
  world,
  as,
}) => {
  const path = { tenant_id: world.tenantId };
  const fact = await ok(
    world.gm.api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'The lich’s tether', slug: 'lich-tether', kinds: ['fact'], parents: [] },
    }),
  );
  const entry = { ...path, entity_id: fact.id };
  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/about/{subject_id}', {
      params: { path: { ...entry, subject_id: world.pia.character.entity_id } },
    }),
  );
  const info = await ok(
    world.gm.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: entry },
      body: {
        title: 'The oath',
        type: 'note',
        locale: 'en-US',
        content: 'The weapon holds his soul.',
        is_public: false,
      },
    }),
  );
  await ok(
    world.gm.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { ...path, entity_id: world.pia.character.entity_id } },
      body: {
        title: 'A reference',
        type: 'note',
        locale: 'en-US',
        content: 'Read [the tether](lich-tether).',
        is_public: true,
      },
    }),
  );
  const page = await as(world.pia);
  const being = `/being/?tenant=${world.tenantId}&id=${world.pia.character.entity_id}`;
  const factUrl = `/fact/?tenant=${world.tenantId}&id=${fact.id}`;
  await page.goto(being);
  await expect(page.getByRole('heading', { name: 'Ashfang', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'The lich’s tether', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'the tether', exact: true })).toHaveCount(0);
  await page.goto(factUrl);
  await expect(page.locator('#fact-status')).toHaveText('This fact is not available.');
  await expect(page.locator('[data-fact-page] h1')).toHaveCount(0);
  const audience = await world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
    params: { path: entry },
  });
  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: entry, header: { 'if-match': audience.response.headers.get('etag') } },
      body: { is_public: false, entity_ids: [world.pia.character.entity_id] },
    }),
  );
  await page.goto(being);
  await expect(page.getByRole('link', { name: 'The lich’s tether', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'the tether', exact: true })).toHaveAttribute(
    'href',
    factUrl,
  );
  await page.getByRole('link', { name: 'The lich’s tether', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'The lich’s tether', exact: true })).toBeVisible();
  await expect(page.getByText('The weapon holds his soul.', { exact: true })).toHaveCount(0);
  const innerPath = { ...path, information_id: info.id };
  const inner = await world.gm.api.GET(
    '/tenants/{tenant_id}/information/{information_id}/audience',
    { params: { path: innerPath } },
  );
  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/information/{information_id}/audience', {
      params: { path: innerPath, header: { 'if-match': inner.response.headers.get('etag') } },
      body: { is_public: false, entity_ids: [world.pia.character.entity_id] },
    }),
  );
  await page.reload();
  await expect(page.getByText('The weapon holds his soul.', { exact: true })).toBeVisible();
  const current = await world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
    params: { path: entry },
  });
  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: entry, header: { 'if-match': current.response.headers.get('etag') } },
      body: { is_public: false, entity_ids: [] },
    }),
  );
  await page.reload();
  await expect(page.locator('#fact-status')).toHaveText('This fact is not available.');
  await expect(page.getByText('The weapon holds his soul.', { exact: true })).toHaveCount(0);
  await page.goto(being);
  await expect(page.locator('[data-being-notes] h3')).toHaveText('A reference');
  await expect(page.getByRole('link', { name: 'The lich’s tether', exact: true })).toHaveCount(0);
});
