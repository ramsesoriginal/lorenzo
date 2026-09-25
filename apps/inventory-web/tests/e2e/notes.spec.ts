import type { Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { API_URL } from './support/env.ts';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { World } from './support/world.ts';

const notes = (page: Page) => page.getByRole('region', { name: 'Notes' });
const note = (page: Page, text: string) =>
  notes(page).getByRole('listitem').filter({ hasText: text });
const itemPage = (world: World, id: string) => `/item/?tenant=${world.tenantId}&id=${id}`;

/** Hands the item to Brisk: another player sees only what their character owns (ADR 0040). */
async function giveToBrisk(world: World, id: string) {
  await ok(
    world.gm.api.PUT('/tenants/{tenant_id}/item-instances/{entity_id}/owner', {
      params: { path: { tenant_id: world.tenantId, entity_id: id } },
      body: { owner_character_id: world.oskar.character.entity_id },
    }),
  );
}

/** Writes a note in whichever Notes region is showing. */
async function addNote(page: Page, text: string, options: { everyone?: boolean } = {}) {
  await notes(page).getByRole('button', { name: 'Add a note' }).click();
  await expect(notes(page).getByLabel('Title')).toHaveValue('Note');
  await notes(page).getByRole('textbox', { name: 'Text' }).fill(text);
  if (options.everyone) await notes(page).getByLabel('Everyone can read this').check();
  await notes(page).getByRole('button', { name: 'Save' }).click();
}

test("a player's note is private: her character's players and the GMs read it", async ({
  world,
  as,
}) => {
  const { spellbook } = await packed(world, world.pia);
  const pia = await as(world.pia);
  await pia.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);
  await pia
    .getByRole('region', { name: 'Backpack' })
    .getByRole('button', { name: 'Ornate Spellbook' })
    .click();

  await expect(notes(pia).getByText('No notes yet.')).toBeVisible();
  await notes(pia).getByRole('button', { name: 'Add a note' }).click();
  await expect(notes(pia).getByLabel('Everyone can read this')).not.toBeChecked();
  await expect(
    notes(pia).getByText("Otherwise only Ashfang's players and the campaign's GMs can."),
  ).toBeVisible();
  await notes(pia).getByRole('textbox', { name: 'Text' }).fill('Smells of *smoke*.');
  await notes(pia).getByRole('button', { name: 'Save' }).click();
  await expect(note(pia, 'Smells of smoke.').getByText('Private')).toBeVisible();
  await expect(note(pia, 'Smells of smoke.').getByRole('heading', { name: 'Note' })).toBeVisible();

  // Once it's Brisk's, Oskar can open it and write about it, but can't read Ashfang's note.
  await giveToBrisk(world, spellbook);
  const oskar = await as(world.oskar);
  await oskar.goto(itemPage(world, spellbook));
  await expect(notes(oskar).getByText('No notes yet.')).toBeVisible();
  await expect(notes(oskar).getByRole('button', { name: 'Add a note' })).toBeVisible();

  const gm = await as(world.gm);
  await gm.goto(itemPage(world, spellbook));
  await expect(note(gm, 'Smells of smoke.')).toBeVisible();
  const information = gm.getByRole('region', { name: 'Information' });
  await expect(information.getByText('note · Private')).toBeVisible();
});

test('a note everyone can read', async ({ world, as }) => {
  const { spellbook } = await packed(world, world.pia);
  const pia = await as(world.pia);
  await pia.goto(itemPage(world, spellbook));
  await addNote(pia, 'Found in the drowned library.', { everyone: true });
  await expect(
    note(pia, 'Found in the drowned library.').getByText('Everyone can read this'),
  ).toBeVisible();

  await giveToBrisk(world, spellbook);
  const oskar = await as(world.oskar);
  await oskar.goto(itemPage(world, spellbook));
  await expect(note(oskar, 'Found in the drowned library.')).toBeVisible();
});

test('edits a note, making it private, and deletes it', async ({ world, as }) => {
  const { spellbook } = await packed(world, world.pia);
  const pia = await as(world.pia);
  await pia.goto(itemPage(world, spellbook));
  await addNote(pia, 'Pages stick together.', { everyone: true });

  await note(pia, 'Pages stick together.').getByRole('button', { name: 'Edit' }).click();
  await notes(pia).getByLabel('Title').fill('Damp');
  await notes(pia).getByLabel('Everyone can read this').uncheck();
  await notes(pia).getByRole('button', { name: 'Save' }).click();
  const edited = note(pia, 'Pages stick together.');
  await expect(edited.getByRole('heading', { name: 'Damp' })).toBeVisible();
  await expect(edited.getByText('Private')).toBeVisible();

  // Private now, and still hers to read after a reload: Ashfang reads it.
  await pia.reload();
  await expect(note(pia, 'Pages stick together.').getByText('Private')).toBeVisible();

  pia.once('dialog', (dialog) => dialog.accept());
  await note(pia, 'Pages stick together.').getByRole('button', { name: 'Delete' }).click();
  await expect(notes(pia).getByText('No notes yet.')).toBeVisible();
});

test("a GM's private note is for the GMs", async ({ world, as }) => {
  const { spellbook } = await packed(world, world.pia);
  const gm = await as(world.gm);
  await gm.goto(itemPage(world, spellbook));

  await notes(gm).getByRole('button', { name: 'Add a note' }).click();
  await expect(notes(gm).getByText("Otherwise only the campaign's GMs can.")).toBeVisible();
  await notes(gm).getByRole('textbox', { name: 'Text' }).fill('A lich wants this back.');
  await notes(gm).getByRole('button', { name: 'Save' }).click();
  await expect(note(gm, 'A lich wants this back.')).toBeVisible();

  const pia = await as(world.pia);
  await pia.goto(itemPage(world, spellbook));
  await expect(notes(pia).getByText('No notes yet.')).toBeVisible();
});

test("keeps no note its reader couldn't be given", async ({ world, as }) => {
  const { spellbook } = await packed(world, world.pia);
  const pia = await as(world.pia);
  await pia.route(`${API_URL}/tenants/*/information/*/knowers/*`, (route) =>
    route.fulfill({ status: 503, json: { detail: 'The knowers are asleep.' } }),
  );
  await pia.goto(itemPage(world, spellbook));

  await addNote(pia, 'Nobody will read this.');
  await expect(notes(pia).getByRole('status').filter({ hasText: "It wasn't kept" })).toContainText(
    'The knowers are asleep.',
  );
  const left = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: {
        path: { tenant_id: world.tenantId, entity_id: spellbook },
        query: { type: ['note'] },
      },
    }),
  );
  expect(left.items).toEqual([]);
});

test('catalog items have no notes section', async ({ world, as }) => {
  const { items } = await packed(world, world.pia);
  const gm = await as(world.gm);
  await gm.goto(itemPage(world, items.ornate));
  await expect(gm.getByRole('heading', { level: 1, name: 'Ornate Spellbook' })).toBeVisible();
  await expect(notes(gm)).toBeHidden();
});
