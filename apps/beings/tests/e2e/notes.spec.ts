import { randomUUID } from 'node:crypto';
import { type Api, ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import { enterMode } from './support/modes.ts';
import { person } from './support/world.ts';

const url = (world: { tenantId: string }, id: string) =>
  `/being/?tenant=${world.tenantId}&id=${id}`;

/** What the viewer's API sees of a being's notes: `title: audience-ish text` lines, in order. */
async function notesSeenBy(
  api: Awaited<ReturnType<typeof import('./support/world.ts').person>>['api'],
  tenantId: string,
  entityId: string,
) {
  const page = await ok(
    api.GET('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { tenant_id: tenantId, entity_id: entityId }, query: { type: ['note'] } },
    }),
  );
  return page.items.map((info) => info.title);
}

test('a GM writes a note for each audience, and each reaches only its readers', async ({
  world,
  as,
}) => {
  const target = world.pia.character.entity_id;
  const page = await as(world.gm);
  await page.goto(url(world, target));

  async function write(label: string, text: string, audience: string, characters: string[] = []) {
    await page.getByRole('button', { name: 'Add a note' }).click();
    const form = page.locator('[data-add-mount] form');
    await form.getByLabel('Label').fill(label);
    await form.getByLabel('Note', { exact: true }).fill(text);
    await form.getByLabel(audience, { exact: true }).check();
    for (const name of characters) await form.getByLabel(name, { exact: true }).check();
    await form.getByRole('button', { name: 'Save' }).click();
    await expect(page.locator('[data-being-notes] h3', { hasText: label })).toBeVisible();
  }

  await write('For the GM', 'Secret.', 'GM only');
  await write('For all', 'Known.', 'Everyone');
  await write('For Brisk', 'Told.', 'Some characters', ['Brisk']);
  await write('For the player', 'Yours.', 'Player note');

  const audiences = page.locator('[data-being-notes] [data-audience]');
  await expect(audiences).toHaveText(['GM only', 'Everyone', 'Some characters', 'Player note']);

  // Pia (who plays Ashfang) reads the public one and the one for her being; Oskar, the public one and
  // the one told to Brisk; neither reads the GM's.
  expect(await notesSeenBy(world.pia.api, world.tenantId, target)).toEqual([
    'For all',
    'For the player',
  ]);
  expect(await notesSeenBy(world.oskar.api, world.tenantId, target)).toEqual([
    'For all',
    'For Brisk',
  ]);
  expect(await notesSeenBy(world.gm.api, world.tenantId, target)).toHaveLength(4);
});

test('a GM edits a note and changes who can read it, then deletes it', async ({ world, as }) => {
  const target = world.pia.character.entity_id;
  await world.note(target, 'Backstory', 'Raised by wolves.');
  const page = await as(world.gm);
  page.on('dialog', (dialog) => void dialog.accept());
  await page.goto(url(world, target));
  await enterMode(page, 'Edit');

  const row = page.locator('[data-being-notes] ul > li', { hasText: 'Backstory' });
  await expect(row.locator('[data-audience]')).toHaveText('GM only');

  await row.getByRole('button', { name: 'Edit' }).click();
  const form = page.locator('[data-being-notes] form');
  await form.getByLabel('Note', { exact: true }).fill('Raised by *crows*.');
  await form.getByLabel('Everyone', { exact: true }).check();
  await form.getByRole('button', { name: 'Save' }).click();

  await expect(row.locator('em')).toHaveText('crows');
  await expect(row.locator('[data-audience]')).toHaveText('Everyone');
  expect(await notesSeenBy(world.oskar.api, world.tenantId, target)).toEqual(['Backstory']);

  await row.getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByText('No notes yet.')).toBeVisible();
});

test('a GM reorders notes', async ({ world, as }) => {
  const target = world.pia.character.entity_id;
  await world.note(target, 'First', 'a');
  await world.note(target, 'Second', 'b');
  await world.note(target, 'Third', 'c');
  const page = await as(world.gm);
  await page.goto(url(world, target));
  await enterMode(page, 'Edit');

  const headings = page.locator('[data-being-notes] h3');
  await expect(headings).toHaveText(['First', 'Second', 'Third']);

  await page
    .locator('[data-being-notes] ul > li', { hasText: 'Third' })
    .getByRole('button', { name: 'Move up' })
    .click();
  await expect(headings).toHaveText(['First', 'Third', 'Second']);
  await page.reload();
  await enterMode(page, 'Edit');
  await expect(headings).toHaveText(['First', 'Third', 'Second']);
  // The first cannot go up, the last cannot go down.
  await expect(page.getByRole('button', { name: 'Move up' }).first()).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Move down' }).last()).toBeDisabled();
});

test('a player writes a Player note on their own being, which their GM reads', async ({
  world,
  as,
}) => {
  const mine = world.pia.character.entity_id;
  const page = await as(world.pia);
  await page.goto(url(world, mine));

  await page.getByRole('button', { name: 'Add a note' }).click();
  const form = page.locator('[data-add-mount] form');
  // A player is offered their own two audiences, Player note first.
  await expect(form.getByRole('radio')).toHaveCount(2);
  await expect(form.getByLabel('Player note')).toBeChecked();
  await form.getByLabel('Note', { exact: true }).fill('I never trusted him.');
  await form.getByRole('button', { name: 'Save' }).click();

  await expect(page.locator('[data-being-notes] [data-audience]')).toHaveText('Player note');
  expect(await notesSeenBy(world.gm.api, world.tenantId, mine)).toEqual(['Note']);
  // Oskar, who plays another character, does not read it.
  expect(await notesSeenBy(world.oskar.api, world.tenantId, mine)).toEqual([]);

  // On a being they do not play, a player reads what is shared and writes nothing.
  await page.goto(url(world, world.oskar.character.entity_id));
  await expect(page.getByRole('button', { name: 'Add a note' })).toBeHidden();
});

// RFC 0038 section 5, ADR 0293: in a repository, a note that is Everyone's goes with every copy and is
// what a person may read before copying it, so it shows a lock and one click to make it GM only.
test("in a repository an Everyone's note shows a lock, and one click makes it GM only", async ({
  as,
}) => {
  const owner = await person('Rhea', ['tenant_creator']);
  const repository = await ok(
    owner.api.POST('/tenants', { body: { name: `Bestiary ${randomUUID()}`, kind: 'repository' } }),
  );
  const path = { tenant_id: repository.id };
  const being = await ok(
    owner.api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'Owlbear', kinds: ['being'], parents: [] },
    }),
  );
  const write = (title: string, content: string, isPublic: boolean) =>
    ok(
      owner.api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { ...path, entity_id: being.id } },
        body: { title, type: 'note', is_public: isPublic, content, locale: 'en' },
      }),
    );
  const open = await write('Habits', 'Hunts at night.', true);

  await write('Weakness', 'Fears fire.', false);

  const page = await as(owner);

  await page.goto(`/being/?tenant=${repository.id}&id=${being.id}`);

  const habits = page.locator('[data-being-notes] ul > li', { hasText: 'Habits' });
  const weakness = page.locator('[data-being-notes] ul > li', { hasText: 'Weakness' });

  await expect(habits.locator('[data-audience]')).toHaveText('Everyone');
  await expect(habits.locator('[data-lock]')).toBeVisible();
  await expect(habits.locator('[data-lock]')).toContainText('Visible to libraries that copy this');
  await expect(weakness.locator('[data-audience]')).toHaveText('GM only');
  await expect(weakness.locator('[data-lock]')).toBeHidden();

  await habits.getByRole('button', { name: 'Make GM only: Habits' }).click();
  await expect(habits.locator('[data-audience]')).toHaveText('GM only');
  await expect(habits.locator('[data-lock]')).toBeHidden();

  // The row is GM only for the API too, and its text is as it was.
  const row = await ok(
    owner.api.GET('/tenants/{tenant_id}/information/{information_id}', {
      params: { path: { ...path, information_id: open.id } },
    }),
  );

  expect(row.is_public).toBe(false);
  await expect(habits).toContainText('Hunts at night.');
});

test("in a library an Everyone's note shows no lock: nothing is copied from it", async ({
  world,
  as,
}) => {
  const target = world.pia.character.entity_id;

  await world.note(target, 'Known', 'To all.', true);

  const page = await as(world.gm);

  await page.goto(url(world, target));
  await expect(page.locator('[data-being-notes] [data-audience]')).toHaveText('Everyone');
  await expect(page.locator('[data-being-notes] [data-lock]')).toBeHidden();
});

// ADR 0294: a campaign's own name for its game master, wherever a note's audience names one.
async function nameTheGm(
  world: { gm: { api: Api }; tenantId: string },
  campaignId: string,
  title: string,
  plural: string,
) {
  await ok(
    world.gm.api.PATCH('/tenants/{tenant_id}/campaigns/{campaign_id}', {
      params: { path: { tenant_id: world.tenantId, campaign_id: campaignId } },
      body: { gm_title: title, gm_title_plural: plural },
    }),
  );
}

test("a note's audiences name the game master by the campaign's title", async ({ world, as }) => {
  const target = world.pia.character.entity_id;

  await nameTheGm(world, world.campaignId, 'Storyteller', 'Storytellers');
  await world.note(target, 'Plot', 'A secret.');

  const page = await as(world.gm);

  await page.goto(url(world, target));

  const audience = page.locator('[data-being-notes] [data-audience]');

  await expect(audience).toHaveText('Storyteller only');

  await page.getByRole('button', { name: 'Add a note' }).click();

  const form = page.locator('[data-add-mount] form');

  // Offered as the title, with what each one means in the plural.
  await expect(form.getByLabel('Storyteller only', { exact: true })).toBeChecked();
  await expect(form.getByText('Only the Storytellers of the campaign can read it.')).toBeVisible();
  await form.getByLabel('Some characters', { exact: true }).check();
  await expect(
    form.getByText('The Storytellers and the characters you choose can read it.'),
  ).toBeVisible();
  await form.getByLabel('Player note', { exact: true }).check();
  await expect(
    form.getByText("The Storytellers and this being's players can read it."),
  ).toBeVisible();
  await expect(page.getByText(/\bGMs?\b/)).toBeHidden();
});

test('a being in two campaigns that name their game master differently says GM', async ({
  world,
  as,
}) => {
  const target = world.pia.character.entity_id;

  await nameTheGm(world, world.campaignId, 'Storyteller', 'Storytellers');
  await nameTheGm(world, world.otherCampaignId, 'Narrator', 'Narrators');

  // Ashfang joins Ash Road too, whose game master has another name.
  const seat = await ok(
    world.gm.api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: world.tenantId, campaign_id: world.otherCampaignId } },
      body: { user_id: world.pia.userId },
    }),
  );

  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/characters/{character_id}/players/{player_id}', {
      params: {
        path: { tenant_id: world.tenantId, character_id: target, player_id: seat.id },
      },
    }),
  );
  await world.note(target, 'Plot', 'A secret.');

  const page = await as(world.gm);

  await page.goto(url(world, target));
  await expect(page.locator('[data-being-notes] [data-audience]')).toHaveText('GM only');

  // The same two campaigns, agreeing, name it again.
  await nameTheGm(world, world.otherCampaignId, 'Storyteller', 'Storytellers');
  await page.reload();
  await expect(page.locator('[data-being-notes] [data-audience]')).toHaveText('Storyteller only');
});

test('a being no campaign holds says GM, whatever its campaigns call theirs', async ({
  world,
  as,
}) => {
  const owl = await world.npc('Owlbear');

  await nameTheGm(world, world.campaignId, 'Storyteller', 'Storytellers');
  await world.note(owl.entity_id, 'Habits', 'Hunts at night.');

  const page = await as(world.gm);

  await page.goto(url(world, owl.entity_id));
  await expect(page.locator('[data-being-notes] [data-audience]')).toHaveText('GM only');
});
