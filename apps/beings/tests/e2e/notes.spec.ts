import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';

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

  const headings = page.locator('[data-being-notes] h3');
  await expect(headings).toHaveText(['First', 'Second', 'Third']);

  await page
    .locator('[data-being-notes] ul > li', { hasText: 'Third' })
    .getByRole('button', { name: 'Move up' })
    .click();
  await expect(headings).toHaveText(['First', 'Third', 'Second']);
  await page.reload();
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
