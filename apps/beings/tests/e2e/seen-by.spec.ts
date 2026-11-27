import { randomUUID } from 'node:crypto';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';

// "Seen by" on a being (ADR 0529) and the Sessions it takes part in (ADR 0531).
test('the game master says who sees a being, and a player outside that no longer finds it', async ({
  world,
  as,
}) => {
  const mara = await world.npc('Mara');
  const gm = await as(world.gm);

  await gm.goto(`/being/?tenant=${world.tenantId}&id=${mara.entity_id}`);
  const seenBy = gm.getByRole('combobox', { name: 'Who sees this being' });

  await expect(seenBy).toHaveValue('everyone');
  await seenBy.selectOption('gm');
  await expect(gm.locator('[data-seen-by-hint]')).toHaveText(
    'Only GMs and whoever plays it see this being.',
  );
  await gm.reload();
  await expect(gm.getByRole('combobox', { name: 'Who sees this being' })).toHaveValue('gm');

  // A player who does not play it is told there is no such being.
  const path = { tenant_id: world.tenantId, character_id: mara.entity_id };
  const hidden = await world.oskar.api.GET('/tenants/{tenant_id}/characters/{character_id}', {
    params: { path },
  });

  expect(hidden.response.status).toBe(404);

  // Opening it again brings it back.
  await gm.getByRole('combobox', { name: 'Who sees this being' }).selectOption('everyone');
  await expect
    .poll(
      async () =>
        (
          await world.oskar.api.GET('/tenants/{tenant_id}/characters/{character_id}', {
            params: { path },
          })
        ).response.status,
    )
    .toBe(200);
});

test('a player who only plays a being is not offered who sees it', async ({ world, as }) => {
  const player = await as(world.pia);

  await player.goto(`/being/?tenant=${world.tenantId}&id=${world.pia.character.entity_id}`);
  await expect(player.getByRole('heading', { name: 'Ashfang', level: 1 })).toBeVisible();
  await expect(player.getByRole('combobox', { name: 'Who sees this being' })).toBeHidden();
});

test('Where it appears lists the Sessions a being came to, which no text names', async ({
  world,
  as,
}) => {
  const path = { tenant_id: world.tenantId };
  const session = await ok(
    world.gm.api.POST('/tenants/{tenant_id}/sessions', {
      params: { path },
      body: {
        id: randomUUID(),
        name: 'At the wreck',
        campaign_id: world.campaignId,
        slug: 'at-the-wreck',
      },
    }),
  );
  const made = await world.gm.api.GET('/tenants/{tenant_id}/sessions/{session_id}', {
    params: { path: { ...path, session_id: session.id } },
  });

  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/sessions/{session_id}/roster', {
      params: {
        path: { ...path, session_id: session.id },
        header: { 'if-match': made.response.headers.get('etag') },
      },
      body: {
        gm_user_ids: [world.gm.userId],
        players: [
          { player_id: world.pia.playerId, character_ids: [world.pia.character.entity_id] },
        ],
      },
    }),
  );

  const gm = await as(world.gm);

  await gm.goto(`/appears/?tenant=${world.tenantId}&id=${world.pia.character.entity_id}`);
  await expect(gm.getByRole('heading', { name: /Sessions it takes part in/ })).toBeVisible();
  await expect(gm.getByText('At the wreck')).toBeVisible();
  await expect(gm.getByText('came to it')).toBeVisible();
});
