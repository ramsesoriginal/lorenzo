import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';

// Where it appears (BN11): what links to a being or a Fact, as far as the viewer may read it.
test('a Fact and a being say where they appear, and a hidden note leaves no trace', async ({
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
  // The Fact is about Ashfang, so Ashfang's player may open it.
  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/about/{subject_id}', {
      params: { path: { ...path, entity_id: fact.id, subject_id: world.pia.character.entity_id } },
    }),
  );
  // Its outer audience is explicit: Ashfang may see it.
  const entry = { ...path, entity_id: fact.id };
  const audience = await world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
    params: { path: entry },
  });
  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: entry, header: { 'if-match': audience.response.headers.get('etag') } },
      body: { is_public: false, entity_ids: [world.pia.character.entity_id] },
    }),
  );
  const note = (title: string, content: string, is_public: boolean) =>
    ok(
      world.gm.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { ...path, entity_id: world.pia.character.entity_id } },
        body: { title, type: 'note', locale: 'en-US', content, is_public },
      }),
    );
  await note('A reference', 'Read [the tether](lich-tether).', true);
  await note('A secret', 'Also [the tether](lich-tether).', false);

  // A player sees the public note's link only.
  const player = await as(world.pia);
  await player.goto(`/fact/?tenant=${world.tenantId}&id=${fact.id}`);
  await player.getByRole('link', { name: 'Where it appears' }).click();
  await expect(
    player.getByRole('heading', { name: 'Where The lich’s tether appears', level: 1 }),
  ).toBeVisible();
  await expect(player.getByRole('heading', { name: /Other entries/ })).toBeVisible();
  await expect(player.getByRole('link', { name: 'Ashfang' })).toBeVisible();
  await expect(player.getByText('A reference')).toBeVisible();
  await expect(player.getByText('A secret')).toHaveCount(0);

  // The GM sees both pieces of information, under the one entry.
  const gm = await as(world.gm);
  await gm.goto(`/appears/?tenant=${world.tenantId}&id=${fact.id}`);
  await expect(gm.getByText('A reference, A secret')).toBeVisible();

  // The way back goes to the Fact.
  await gm.getByRole('link', { name: '← The lich’s tether' }).click();
  await expect(gm).toHaveURL(/\/fact\//);

  // A being nothing links to says so, and its page has the way in.
  await gm.goto(`/being/?tenant=${world.tenantId}&id=${world.oskar.character.entity_id}`);
  await gm.getByRole('link', { name: 'Where it appears' }).click();
  await expect(gm.getByRole('heading', { name: 'Where Brisk appears', level: 1 })).toBeVisible();
  await expect(gm.getByText('Nothing links here yet.')).toBeVisible();
});

test('the page asks to log in, and says so for something that is not there', async ({
  world,
  as,
  page,
}) => {
  await page.goto(`/appears/?tenant=${world.tenantId}&id=${world.pia.character.entity_id}`);
  await expect(page.getByText("You're not logged in. Log in to continue.")).toBeVisible();

  const signedIn = await as(world.gm);
  await signedIn.goto(`/appears/?tenant=${world.tenantId}&slug=no-such-entry`);
  await expect(signedIn.getByText('This entry is not available.')).toBeVisible();
});
