import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';
import { ok } from './support/api.ts';
import { signedIn, world } from './support/world.ts';

/**
 * What axe finds on the page, apart from one known thing outside this app: the "1." toolbar button
 * of packages/lorenzoscript-editor is named "Numbered list", which does not contain its visible text.
 */
async function violations(page: Page) {
  return (await new AxeBuilder({ page }).analyze()).violations.filter(
    (v) =>
      !(
        v.id === 'label-content-name-mismatch' &&
        v.nodes.every((n) => n.target.join(' ').includes('Numbered list'))
      ),
  );
}

test('a GM writes a note with a picture on a relationship, opens it to the library and changes it', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.person('Mara Quill');
  const b = await w.person('Wren Ashdown');
  const tie = await w.tie('Mara is the parent of Wren', a.id, b.id, true);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationship/?tenant=${w.tenant.id}&id=${tie.id}`);
  const notes = page.getByRole('region', { name: 'Notes' });
  await expect(notes.getByText('No notes are available to you here.')).toBeVisible();

  const png = await page.screenshot();
  await notes.getByRole('button', { name: 'Add note' }).click();
  const form = notes.locator('form');
  await form.getByLabel('Note title').fill('How the tie was sworn');
  await form.getByLabel('Note', { exact: true }).fill('It was sworn at **dawn**.');
  await form
    .locator('input[type=file]')
    .setInputFiles({ name: 'oath.png', mimeType: 'image/png', buffer: png });
  await form.getByRole('button', { name: 'Save note' }).click();

  const note = notes.getByRole('article').filter({ hasText: 'How the tie was sworn' });
  await expect(note.locator('strong', { hasText: 'dawn' })).toBeVisible();
  await expect(note.locator('img')).toBeVisible();
  await expect(note.getByText('Restricted')).toBeVisible();

  // The note's own audience: opened to the library.
  await note.getByText('Who can read this').click();
  await note.getByLabel('Everyone with access to the library').check();
  await note.getByRole('button', { name: 'Save audience' }).click();
  await expect(note.getByText('Everyone in this library')).toBeVisible();

  // Changed in place, keeping its audience.
  await note.getByRole('button', { name: 'Edit note' }).click();
  await notes.getByLabel('Note', { exact: true }).fill('It was sworn at **dusk**.');
  await notes.getByRole('button', { name: 'Save note' }).click();
  await expect(notes.locator('strong', { hasText: 'dusk' })).toBeVisible();
  await expect(notes.getByText('Everyone in this library')).toBeVisible();
  await page.reload();
  await expect(notes.locator('strong', { hasText: 'dusk' })).toBeVisible();
});

test('a GM writes a note on a web, and a player reads the shared one and changes nothing', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const web = await ok(
    w.gm.POST('/tenants/{tenant_id}/social-webs', {
      params: { path: w.path },
      body: { name: 'The court', is_public: true, layout: 'circle', layout_seed: 1 },
    }),
  );
  await w.tie('Open friendship', a.id, (await w.entry('Wren Ashdown')).id, true);
  const gm = await signedIn(browser, w.subject);
  await gm.goto(`/web/?tenant=${w.tenant.id}&id=${web.id}`);
  const notes = gm.getByRole('region', { name: 'Notes' });
  await notes.getByRole('button', { name: 'Add note' }).click();
  await notes.getByLabel('Note title').fill('Who sits where');
  await notes.getByLabel('Note', { exact: true }).fill('The queen sits *last*.');
  await notes.getByRole('button', { name: 'Save note' }).click();
  const note = notes.getByRole('article').filter({ hasText: 'Who sits where' });
  await expect(note.locator('em', { hasText: 'last' })).toBeVisible();
  await note.getByText('Who can read this').click();
  await note.getByLabel('Everyone with access to the library').check();
  await note.getByRole('button', { name: 'Save audience' }).click();
  await expect(note.getByText('Everyone in this library')).toBeVisible();

  const player = await signedIn(browser, w.playerSubject);
  await player.goto(`/web/?tenant=${w.tenant.id}&id=${web.id}`);
  const seen = player.getByRole('region', { name: 'Notes' });
  await expect(seen.locator('em', { hasText: 'last' })).toBeVisible();
  await expect(seen.getByRole('button', { name: 'Edit note' })).toHaveCount(0);
});

test('a restricted note is not shown to a player', async ({ browser }) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  const tie = await w.tie('Open friendship', a.id, b.id, true);
  const gm = await signedIn(browser, w.subject);
  await gm.goto(`/relationship/?tenant=${w.tenant.id}&id=${tie.id}`);
  const notes = gm.getByRole('region', { name: 'Notes' });
  await notes.getByRole('button', { name: 'Add note' }).click();
  await notes.getByLabel('Note title').fill('For the GM only');
  await notes.getByLabel('Note', { exact: true }).fill('A secret.');
  await notes.getByRole('button', { name: 'Save note' }).click();
  await expect(notes.getByText('A secret.')).toBeVisible();

  const player = await signedIn(browser, w.playerSubject);
  await player.goto(`/relationship/?tenant=${w.tenant.id}&id=${tie.id}`);
  const seen = player.getByRole('region', { name: 'Notes' });
  await expect(seen.getByText('No notes are available to you here.')).toBeVisible();
  await expect(player.getByText('A secret.')).toHaveCount(0);
});

for (const theme of ['light', 'dark'] as const) {
  test(`a relationship with a note and its form has no axe violations in ${theme}`, async ({
    browser,
  }) => {
    const w = await world();
    const a = await w.entry('Mara Quill');
    const b = await w.entry('Wren Ashdown');
    const tie = await w.tie('Open friendship', a.id, b.id, true);
    const page = await signedIn(browser, w.subject, theme);
    await page.goto(`/relationship/?tenant=${w.tenant.id}&id=${tie.id}`);
    const notes = page.getByRole('region', { name: 'Notes' });
    await notes.getByRole('button', { name: 'Add note' }).click();
    await notes.getByLabel('Note title').fill('A note');
    await notes.getByLabel('Note', { exact: true }).fill('Some words.');
    await notes.getByRole('button', { name: 'Save note' }).click();
    await expect(notes.getByText('Some words.')).toBeVisible();
    await notes.getByText('Who can read this').click();
    await expect(notes.getByLabel('Everyone with access to the library')).toBeVisible();
    expect(await violations(page)).toEqual([]);
    await notes.getByRole('button', { name: 'Edit note' }).click();
    await expect(notes.getByRole('button', { name: 'Save note' })).toBeVisible();
    expect(await violations(page)).toEqual([]);
  });
}

test('on a phone the notes fit the width', async ({ browser }) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  const tie = await w.tie('Open friendship', a.id, b.id, true);
  const page = await signedIn(browser, w.subject);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/relationship/?tenant=${w.tenant.id}&id=${tie.id}`);
  const notes = page.getByRole('region', { name: 'Notes' });
  await notes.getByRole('button', { name: 'Add note' }).click();
  await expect(notes.getByLabel('Note title')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
