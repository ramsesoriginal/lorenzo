// What a campaign calls its game master (ADR 0294): the texts about its characters and items say
// it, and the library's own pages keep saying "GM".
import type { Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { World } from './support/world.ts';

async function nameTheGm(world: World, gm_title: string, gm_title_plural: string) {
  await ok(
    world.gm.api.PATCH('/tenants/{tenant_id}/campaigns/{campaign_id}', {
      params: { path: { tenant_id: world.tenantId, campaign_id: world.campaignId } },
      body: { gm_title, gm_title_plural },
    }),
  );
}

const card = (page: Page) => page.getByRole('region', { name: 'Add an item' });
const notes = (page: Page) => page.getByRole('region', { name: 'Notes' });
const itemPage = (world: World, id: string) => `/item/?tenant=${world.tenantId}&id=${id}`;

test("the add-an-item card says the campaign's title for its game master", async ({
  world,
  as,
}) => {
  await world.item('Shortsword', { public: true });
  await nameTheGm(world, 'Storyteller', 'Storytellers');
  await ok(
    world.gm.api.PATCH('/tenants/{tenant_id}/campaigns/{campaign_id}', {
      params: { path: { tenant_id: world.tenantId, campaign_id: world.campaignId } },
      body: { player_self_service: false },
    }),
  );

  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);

  await expect(
    card(page).getByText('Your Storyteller has switched off adding items for Ashfang.'),
  ).toBeVisible();
  await expect(page.getByText('Your GM')).toBeHidden();
});

test('the unsorted hints say it too', async ({ world, as }) => {
  await world.item('Rope', { public: true });
  await nameTheGm(world, 'Narrator', 'Narrators');

  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);

  await expect(card(page).getByText(/Ask your Narrator to run/)).toBeVisible();
});

test("a private note names the owner's campaign's game masters by its title", async ({
  world,
  as,
}) => {
  const { spellbook } = await packed(world, world.pia);
  await nameTheGm(world, 'Storyteller', 'Storytellers');

  const gm = await as(world.gm);
  await gm.goto(itemPage(world, spellbook));
  await notes(gm).getByRole('button', { name: 'Add a note' }).click();
  await expect(
    notes(gm).getByText("Otherwise only the campaign's Storytellers can."),
  ).toBeVisible();

  const pia = await as(world.pia);
  await pia.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);
  await pia
    .getByRole('region', { name: 'Backpack' })
    .getByRole('button', { name: 'Ornate Spellbook' })
    .click();
  await notes(pia).getByRole('button', { name: 'Add a note' }).click();
  await expect(
    notes(pia).getByText("Otherwise only Ashfang's players and the campaign's Storytellers can."),
  ).toBeVisible();
});

test('what no campaign holds says GMs, and so do the catalog and the unsorted page', async ({
  world,
  as,
}) => {
  const rope = await world.item('Rope', { public: true });
  const lying = await world.instance(rope);
  await nameTheGm(world, 'Storyteller', 'Storytellers');

  const gm = await as(world.gm);
  await gm.goto(itemPage(world, lying));
  await notes(gm).getByRole('button', { name: 'Add a note' }).click();
  await expect(notes(gm).getByText("Otherwise only the campaign's GMs can.")).toBeVisible();

  const pia = await as(world.pia);
  await pia.goto(`/items/?tenant=${world.tenantId}`);
  await expect(pia.getByText('Everything your GMs have put in the public catalog.')).toBeVisible();
  await pia.goto(`/unsorted/?tenant=${world.tenantId}`);
  await expect(pia.getByText('Sorting unsorted items is for a GM.')).toBeVisible();
});
