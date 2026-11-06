import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { ok } from './support/api.ts';
import { signedIn, world } from './support/world.ts';

async function webOf(w: Awaited<ReturnType<typeof world>>, name: string, members: string[]) {
  const made = await ok(
    w.gm.POST('/tenants/{tenant_id}/social-webs', {
      params: { path: w.path },
      body: { name, is_public: true, layout: 'circle', layout_seed: 1 },
    }),
  );
  const tag = (
    await w.gm.GET('/tenants/{tenant_id}/social-webs/{web_id}', {
      params: { path: { ...w.path, web_id: made.id } },
    })
  ).response.headers.get('etag');
  await ok(
    w.gm.POST('/tenants/{tenant_id}/social-webs/{web_id}/members/bulk', {
      params: { path: { ...w.path, web_id: made.id } },
      headers: { 'If-Match': tag ?? '' },
      body: { set: members.map((entry_id) => ({ entry_id })) },
    }),
  );
  return made;
}

test('a GM makes a web, adds entries and sees them drawn with a sentence a relationship', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  await w.entry('Dren Holloway');
  await w.tie('Mara is the parent of Wren', a.id, b.id, true);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/webs/?tenant=${w.tenant.id}`);
  await expect(page.getByText('There are no webs you can see yet.')).toBeVisible();
  const form = page.getByRole('form', { name: 'Make a web' });
  await form.getByLabel('Name').fill('The court');
  await form.getByLabel('Layout').selectOption('stress');
  await form.getByLabel('Everyone in the library may see it').check();
  await form.getByRole('button', { name: 'Make the web' }).click();
  await expect(page.getByRole('heading', { name: 'The court', level: 1 })).toBeVisible();
  await expect(page.getByText('This web shows no entries yet.')).toBeVisible();

  for (const [search, label] of [
    ['Mara', 'Mara Quill'],
    ['Wren', 'Wren Ashdown'],
  ] as const) {
    await page.getByLabel('Add an entry: search by name').fill(search);
    await page.getByLabel('Add an entry: results').selectOption({ label });
    await page.getByRole('button', { name: 'Add it to the web' }).click();
    await expect(page.getByRole('button', { name: `Take out ${label}` })).toBeVisible();
  }
  // The drawing: each entry a button, and the relationship told in words beside it.
  const drawing = page.getByRole('group', { name: 'The court' });
  await expect(drawing.getByRole('button', { name: 'Mara Quill' })).toBeVisible();
  await expect(drawing.getByRole('button', { name: 'Wren Ashdown' })).toBeVisible();
  const sentences = page.getByRole('list', { name: 'Relationships in this web' });
  await expect(sentences.getByRole('link', { name: 'Mara is the parent of Wren' })).toBeVisible();
  await expect(
    sentences.getByText('Between Mara Quill and Wren Ashdown, both ways.'),
  ).toBeVisible();

  // Selecting a node says so, and the layout changes without losing the entries.
  await drawing.getByRole('button', { name: 'Mara Quill' }).focus();
  await page.keyboard.press('Space');
  await expect(page.getByText('Selected Mara Quill.')).toBeVisible();
  await page.getByLabel('Layout').selectOption('forceatlas2');
  await expect(drawing.getByRole('button', { name: 'Wren Ashdown' })).toBeVisible();
  await page.getByRole('button', { name: 'Save how it is drawn' }).click();
  await expect(page.getByText('Saved how it is drawn.')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Layout')).toHaveValue('forceatlas2');
});

test('a player reads a web without the members and relationships they may not see', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  const hidden = await w.entry('The sealed vault', false);
  await w.tie('Open friendship', a.id, b.id, true);
  await w.tie('Cut tie', a.id, hidden.id, true);
  const made = await webOf(w, 'The court', [a.id, b.id, hidden.id]);
  const page = await signedIn(browser, w.playerSubject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}`);
  await expect(page.getByRole('heading', { name: 'The court', level: 1 })).toBeVisible();
  await expect(page.getByText('2 entries and 1 relationship')).toBeVisible();
  await expect(page.getByText('sealed vault')).toHaveCount(0);
  await expect(page.getByText('Cut tie')).toHaveCount(0);
  await expect(page.getByText('Add an entry')).toHaveCount(0);
});

for (const theme of ['light', 'dark'] as const) {
  test(`a web and the list of webs have no axe violations in ${theme}`, async ({ browser }) => {
    const w = await world();
    const a = await w.entry('Mara Quill');
    const b = await w.entry('Wren Ashdown');
    await w.tie('Open friendship', a.id, b.id, true);
    const made = await webOf(w, 'The court', [a.id, b.id]);
    const page = await signedIn(browser, w.subject, theme);
    await page.goto(`/webs/?tenant=${w.tenant.id}`);
    await expect(page.getByRole('link', { name: 'The court' })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}`);
    await expect(page.getByRole('group', { name: 'The court' })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });
}

test('on a phone the web fits the width and its controls are tall enough to press', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  await w.tie('Open friendship', a.id, b.id, true);
  const made = await webOf(w, 'The court', [a.id, b.id]);
  const page = await signedIn(browser, w.subject);
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}`);
  await expect(page.getByRole('group', { name: 'The court' })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  const box = await page.getByRole('button', { name: 'Zoom in' }).boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
});
