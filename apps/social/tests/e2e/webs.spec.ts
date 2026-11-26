import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { ok } from './support/api.ts';
import { signedIn, standing, world } from './support/world.ts';

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
  const a = await w.person('Mara Quill');
  const b = await w.person('Wren Ashdown');
  await w.person('Dren Holloway');
  await w.tie('Mara is the parent of Wren', a.id, b.id, true);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/webs/?tenant=${w.tenant.id}`);
  await expect(page.getByText('There are no webs you can see yet.')).toBeVisible();
  await page.getByRole('button', { name: 'New web' }).first().click();
  const form = page.getByRole('form', { name: 'Make a web' });
  await form.getByLabel('Name').fill('The court');
  await form.getByLabel('Layout').selectOption('stress');
  await form.getByLabel('Everyone in the library may see it').check();
  await form.getByRole('button', { name: 'Make the web' }).click();
  await expect(page.getByRole('heading', { name: 'The court', level: 1 })).toBeVisible();
  await expect(page.getByText('This web shows no entries yet.')).toBeVisible();

  await page.getByRole('button', { name: 'Members' }).click();
  for (const [search, label] of [
    ['Mara', 'Mara Quill'],
    ['Wren', 'Wren Ashdown'],
  ] as const) {
    await page.getByLabel('Add an entry: search by name').fill(search);
    await page.getByLabel('Add an entry: results').selectOption({ label });
    await page.getByRole('button', { name: 'Add it to the web' }).click();
    await expect(page.getByRole('button', { name: `Take out ${label}` })).toBeVisible();
  }
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  // The drawing: each entry a button, and the relationship told in words beside it.
  const drawing = page.getByRole('group', { name: 'The court' });
  await expect(drawing.getByRole('button', { name: 'Mara Quill' })).toBeVisible();
  await expect(drawing.getByRole('button', { name: 'Wren Ashdown' })).toBeVisible();
  // The List view tells each relationship in a sentence.
  await page.getByRole('group', { name: 'View' }).getByRole('button', { name: 'List' }).click();
  const sentences = page.getByRole('list', { name: 'Relationships in this web' });
  await expect(sentences.getByRole('link', { name: 'Mara is the parent of Wren' })).toBeVisible();
  await expect(
    sentences.getByText('Between Mara Quill and Wren Ashdown, both ways.'),
  ).toBeVisible();
  await page.getByRole('group', { name: 'View' }).getByRole('button', { name: 'Graph' }).click();

  // Selecting a node says so and opens it in the panel, and the layout changes without losing the entries.
  await drawing.getByRole('button', { name: 'Mara Quill' }).focus();
  await page.keyboard.press('Space');
  await expect(page.getByText('Selected Mara Quill.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Mara Quill', level: 2 })).toBeVisible();
  await page.getByRole('button', { name: 'Drawing' }).click();
  await page.getByLabel('Layout').selectOption('forceatlas2');
  await expect(drawing.getByRole('button', { name: 'Wren Ashdown' })).toBeVisible();
  await page.getByRole('button', { name: 'Save how it is drawn' }).click();
  await expect(page.getByText('Saved how it is drawn.')).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Drawing' }).click();
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

test('the date lens draws what holds, dots what is not known and lists the rest under a switch', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  const before = await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'The wedding', kinds: ['event'], parents: [] },
    }),
  );
  const later = await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'The war', kinds: ['event'], parents: [] },
    }),
  );
  const tag = (
    await w.gm.GET('/tenants/{tenant_id}/events/{event_id}/relationships', {
      params: { path: { ...w.path, event_id: before.id } },
    })
  ).response.headers.get('etag');
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/events/{event_id}/relationships/{other_event_id}', {
      params: { path: { ...w.path, event_id: before.id, other_event_id: later.id } },
      headers: { 'If-Match': tag ?? '' },
      body: { kind: 'causes', direction: 'outgoing' },
    }),
  );
  await w.tie('Always friends', a.id, b.id, true);
  await ok(
    w.gm.POST('/tenants/{tenant_id}/relationships', {
      params: { path: w.path },
      body: {
        name: 'Rivals once the war began',
        end_a: a.id,
        end_b: b.id,
        one_way: false,
        is_public: true,
        starts_at: later.id,
      },
    }),
  );
  const made = await webOf(w, 'The court', [a.id, b.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}&as_of=${before.id}&view=list`);
  // A line says what the lens has on.
  await expect(page.getByText('Looking as of The wedding')).toBeVisible();
  const sentences = page.getByRole('list', { name: 'Relationships in this web' });
  await expect(sentences.getByRole('link', { name: 'Always friends' })).toBeVisible();
  // It has not begun yet: not drawn, and listed only under the switch.
  await expect(sentences.getByRole('link', { name: 'Rivals once the war began' })).toHaveCount(0);
  await expect(
    page.getByText('1 relationship has not begun or has ended, and is not drawn'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'List them' }).click();
  await expect(sentences.getByText('Has not begun.')).toBeVisible();
  // And it is drawn, faded, while the switch is on.
  await expect(page.locator('.gr-edge.is-dim').first()).toBeAttached();
  await expect(page.getByText(/is shown faded/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'As of an Event' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  // The lens is part of the address, and can be removed.
  await page.getByRole('button', { name: 'Clear the date lens' }).click();
  await expect(page.getByText('Looking as of The wedding')).toHaveCount(0);
  expect(page.url()).not.toContain('as_of=');
});

test('a family tree is drawn in rows with right angles when the layered layout and theme are chosen', async ({
  browser,
}) => {
  const w = await world();
  const gran = await w.entry('Tomas Ashdown');
  const mara = await w.entry('Mara Quill');
  const wren = await w.entry('Wren Quill');
  await ok(
    w.gm.POST('/tenants/{tenant_id}/relationships', {
      params: { path: w.path },
      body: {
        name: 'Tomas is the parent of Mara',
        end_a: gran.id,
        end_b: mara.id,
        one_way: true,
        is_public: true,
      },
    }),
  );
  await ok(
    w.gm.POST('/tenants/{tenant_id}/relationships', {
      params: { path: w.path },
      body: {
        name: 'Mara is the parent of Wren',
        end_a: mara.id,
        end_b: wren.id,
        one_way: true,
        is_public: true,
      },
    }),
  );
  const made = await webOf(w, 'The Quills', [gran.id, mara.id, wren.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}`);
  const drawing = page.getByRole('group', { name: 'The Quills' });
  await expect(drawing.getByRole('button', { name: 'Tomas Ashdown' })).toBeVisible();
  await page.getByRole('button', { name: 'Drawing' }).click();
  await page.getByRole('combobox', { name: /^Layout/ }).selectOption('layered');
  await page.getByRole('combobox', { name: /^Theme/ }).selectOption('family');
  const y = async (name: string) =>
    Number(await drawing.getByRole('button', { name }).locator('circle').getAttribute('cy'));
  expect(await y('Tomas Ashdown')).toBeLessThan(await y('Mara Quill'));
  expect(await y('Mara Quill')).toBeLessThan(await y('Wren Quill'));
  const edge = drawing.locator('path.gr-edge').first();
  expect(((await edge.getAttribute('d')) ?? '').match(/L/g)?.length).toBe(3);
});

test('Home opens the webs of the library, continues the last web, renames and deletes one', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const made = await webOf(w, 'The court', [a.id]);
  await webOf(w, 'The guild', [a.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Webs', level: 1 })).toBeVisible();
  await expect(page.getByRole('link', { name: 'The court' })).toBeVisible();

  // Opening a web makes Home offer it again.
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}`);
  await expect(page.getByRole('group', { name: 'The court' })).toBeVisible();
  await page.goto('/');
  await expect(
    page.getByRole('region', { name: 'Continue' }).getByRole('link', { name: 'The court' }),
  ).toBeVisible();

  // A rename is in place; a delete asks first and names what stays.
  await page.getByRole('button', { name: 'Rename The guild' }).click();
  const rename = page.getByRole('form', { name: 'Rename the web' });
  await rename.getByLabel('Name').fill('The order');
  await rename.getByRole('button', { name: 'Rename' }).click();
  await expect(page.getByRole('link', { name: 'The order' })).toBeVisible();
  await page.getByRole('button', { name: 'Delete The order' }).click();
  await expect(
    page.getByText('The entries and their relationships stay as they are.'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Delete the web' }).click();
  await expect(page.getByRole('link', { name: 'The order' })).toHaveCount(0);
  await expect(
    page.getByRole('list', { name: 'Webs' }).getByRole('link', { name: 'The court' }),
  ).toBeVisible();
});

test('Focus dims all but the selected entry and its neighbours, and the view is kept in the address', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  const c = await w.entry('Dren Holloway');
  await w.tie('Open friendship', a.id, b.id, true);
  const made = await webOf(w, 'The court', [a.id, b.id, c.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}`);
  const drawing = page.getByRole('group', { name: 'The court' });
  await expect(drawing.getByRole('button', { name: 'Dren Holloway' })).toBeVisible();

  // With nothing selected Focus says so, and dims nothing.
  await page.getByRole('button', { name: 'Focus' }).click();
  await expect(page.getByText('Focus needs a selection')).toBeVisible();
  await expect(page.locator('.gr-node.is-dim')).toHaveCount(0);

  await drawing.getByRole('button', { name: 'Mara Quill' }).focus();
  await page.keyboard.press('Space');
  await expect(page.locator('.gr-node.is-dim')).toHaveCount(1);
  await expect(
    drawing.getByRole('button', { name: 'Dren Holloway' }).locator('.is-dim'),
  ).not.toHaveCount(0);

  await page.getByRole('button', { name: 'Focus' }).click();
  await expect(page.locator('.gr-node.is-dim')).toHaveCount(0);

  await page.getByRole('group', { name: 'View' }).getByRole('button', { name: 'List' }).click();
  expect(page.url()).toContain('view=list');
});

test('Members adds a group’s members and everyone within steps, and Connect ties two entries from the page', async ({
  browser,
}) => {
  const w = await world();
  const mara = await w.person('Mara Quill');
  const wren = await w.person('Wren Ashdown');
  const dren = await w.person('Dren Holloway');
  const far = await w.person('Far Away');
  await w.group('The Court', mara.id);
  await w.tie('Mara knows Wren', mara.id, wren.id, true);
  await w.tie('Wren knows Dren', wren.id, dren.id, true);
  const made = await webOf(w, 'The court', [mara.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}`);
  const drawing = page.getByRole('group', { name: 'The court' });
  await expect(drawing.getByRole('button', { name: 'Mara Quill' })).toBeVisible();

  // Everyone within one step of the selected entry.
  await drawing.getByRole('button', { name: 'Mara Quill' }).focus();
  await page.keyboard.press('Space');
  await page.getByRole('button', { name: 'Members' }).click();
  const dialog = page.getByRole('group', { name: 'Members' });
  await dialog.getByLabel('Steps').selectOption('1');
  await dialog.getByRole('button', { name: 'Add everyone near Mara Quill' }).click();
  await expect(dialog.getByText('Within 1 of Mara Quill: added 1.')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Take out Wren Ashdown' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Take out Dren Holloway' })).toHaveCount(0);

  // A group's members are added, and one already in the web is not doubled.
  await dialog.getByLabel('Add the members of a group: search by name').fill('Court');
  await dialog
    .getByLabel('Add the members of a group: results')
    .selectOption({ label: 'The Court' });
  await dialog.getByRole('button', { name: 'Add its members' }).click();
  await expect(dialog.getByText('They are all in the web already.')).toBeVisible();
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();

  // Connect does not offer the same entry twice, and says so in words; it ties two entries without leaving the page.
  await page.getByRole('button', { name: 'Connect' }).click();
  const form = page.getByRole('form', { name: 'Connect two entries' });
  await form.getByLabel('First end: search by name').fill('Dren');
  await form.getByLabel('First end: results').selectOption({ label: dren.name });
  await form.getByLabel('Second end: search by name').fill('Dren');
  await expect(form.getByText('No being or group by that name.')).toBeVisible();
  await form.getByLabel('Second end: search by name').fill('Far');
  await form.getByLabel('Second end: results').selectOption({ label: far.name });
  await form.getByLabel('Name (optional)').fill('Dren owes Far');
  await form.getByRole('button', { name: 'Make the relationship' }).click();
  await expect(drawing.getByRole('button', { name: 'Far Away' })).toBeVisible();
  expect(page.url()).toContain('/web/');
});

test('"as read by" is a switch with a line that says what is on and clears it', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.person('Mara Quill');
  const b = await w.person('Wren Ashdown');
  await w.tie('Open friendship', a.id, b.id, true);
  const made = await webOf(w, 'The court', [a.id, b.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}&as_seen_by=${a.id}`);
  await expect(
    page.getByText('As read by Mara Quill: what it may read, not what it believes'),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'As read by' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.getByRole('button', { name: 'Clear the reader' }).click();
  await expect(page.getByText('As read by Mara Quill')).toHaveCount(0);
  expect(page.url()).not.toContain('as_seen_by=');
  await expect(page.getByRole('button', { name: 'As read by' })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
});

test('the panel reads a relationship: its type, standings with their scale, and since and until', async ({
  browser,
}) => {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  const wedding = await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'The wedding', kinds: ['event'], parents: [] },
    }),
  );
  const tie = await ok(
    w.gm.POST('/tenants/{tenant_id}/relationships', {
      params: { path: w.path },
      body: {
        name: 'Mara trusts Wren',
        end_a: a.id,
        end_b: b.id,
        one_way: false,
        is_public: true,
        starts_at: wedding.id,
      },
    }),
  );
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: { path: { ...w.path, entity_id: tie.id, stat_definition_id: honor.id } },
      body: { value: 5, acquire_group: true },
    }),
  );
  const made = await webOf(w, 'The court', [a.id, b.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}&view=list`);
  await page.getByRole('button', { name: 'Read Mara trusts Wren in the panel' }).click();
  const panel = page.getByRole('complementary', { name: 'The web’s panel' });
  await expect(panel.getByText('It has no type.')).toBeVisible();
  await expect(panel.getByText('Since The wedding.')).toBeVisible();
  const standings = panel.getByRole('list', { name: 'Standings of this relationship' });
  await expect(standings.getByText('Honor')).toBeVisible();
  await expect(standings.locator('.standing-num')).toHaveText('5');
  await expect(standings.getByText('from -10 to 10')).toBeVisible();
  // A standing is changed where it is read, refused outside its scale, and has Undo.
  const input = panel.getByLabel('Honor of Mara trusts Wren');
  await input.fill('12');
  await input.press('Tab');
  await expect(panel.getByText('12 is above the scale (up to 10).')).toBeVisible();
  await input.fill('8');
  await input.press('Tab');
  await expect(page.getByText('Honor of Mara trusts Wren is 8')).toBeVisible();
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(input).toHaveValue('5');
  // The same selection is in the drawing.
  await page.getByRole('group', { name: 'View' }).getByRole('button', { name: 'Graph' }).click();
  await expect(panel.getByRole('heading', { name: 'Mara trusts Wren' })).toBeVisible();
});

test('Groups outlines a group, Steps shows only what is near the selection, and a standing shows on the lines', async ({
  browser,
}) => {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const mara = await w.person('Mara Quill');
  const wren = await w.person('Wren Ashdown');
  const dren = await w.person('Dren Holloway');
  const far = await w.person('Far Away');
  const court = await w.group('The Court', mara.id);
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/groups/{group_entity_id}/members/{character_entity_id}', {
      params: {
        path: { ...w.path, group_entity_id: court.id, character_entity_id: wren.id },
      },
    }),
  );
  const tie = await w.tie('Mara knows Wren', mara.id, wren.id, true);
  await w.tie('Wren knows Dren', wren.id, dren.id, true);
  await w.tie('Dren knows Far', dren.id, far.id, true);
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: { path: { ...w.path, entity_id: tie.id, stat_definition_id: honor.id } },
      body: { value: 6, acquire_group: true },
    }),
  );
  const made = await webOf(w, 'The court', [mara.id, wren.id, dren.id, far.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${made.id}`);
  const drawing = page.getByRole('group', { name: 'The court' });
  await expect(drawing.getByRole('button', { name: 'Far Away' })).toBeVisible();

  // The standing is chosen, saved, and then told on the line.
  await page.getByRole('button', { name: 'Drawing' }).click();
  await page.getByLabel('Standing shown on the lines').selectOption(honor.id);
  await page.getByRole('button', { name: 'Save how it is drawn' }).click();
  await expect(page.getByText('Mara knows Wren: 6')).toBeVisible();
  await page.getByRole('button', { name: 'Close the panel' }).click();

  // Steps: one step from Wren leaves Mara and Dren, not Far Away.
  await page.getByRole('button', { name: /^Steps/ }).click();
  await expect(page.getByText('Steps are counted from a selection')).toBeVisible();
  await drawing.getByRole('button', { name: 'Wren Ashdown' }).focus();
  await page.keyboard.press('Space');
  await page.getByRole('button', { name: 'Close the panel' }).click();
  await page.getByRole('button', { name: /^Steps/ }).click();
  await expect(page.getByRole('button', { name: 'Steps: 1' })).toBeVisible();
  await expect(drawing.getByRole('button', { name: 'Far Away' })).toHaveCount(0);
  await expect(drawing.getByRole('button', { name: 'Dren Holloway' })).toBeVisible();
  await page.getByRole('button', { name: /^Steps/ }).click();
  await page.getByRole('button', { name: /^Steps/ }).click();
  await expect(drawing.getByRole('button', { name: 'Far Away' })).toBeVisible();

  // Groups: the group's two members in the web are outlined.
  await page.getByRole('button', { name: 'Groups' }).click();
  await expect(page.locator('.gr-hull').first()).toBeAttached();
});

test('a line is labelled with its type, a chain is dashed, and a hand-placed entry moves by keys and by number', async ({
  browser,
}) => {
  const w = await world();
  const wren = await w.entry('Wren Ashdown');
  const mara = await w.entry('Mara Quill');
  const tomas = await w.entry('Tomas Ashdown');
  const parent = await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'Parent of', kinds: [], parents: [] },
    }),
  );
  const made1 = await ok(
    w.gm.POST('/tenants/{tenant_id}/relationships', {
      params: { path: w.path },
      body: {
        name: 'Wren and Mara',
        end_a: wren.id,
        end_b: mara.id,
        one_way: true,
        is_public: true,
        prototypes: [parent.id],
      },
    }),
  );
  const up = await w.tie('Mara and Tomas', mara.id, tomas.id, true);
  const grand = await w.tie('Wren and Tomas', wren.id, tomas.id, true);
  const path = { ...w.path, relationship_id: grand.id };
  const tag = (
    await w.gm.GET('/tenants/{tenant_id}/relationships/{relationship_id}/through', {
      params: { path },
    })
  ).response.headers.get('etag');
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/relationships/{relationship_id}/through', {
      params: { path },
      headers: { 'If-Match': tag ?? '' },
      body: { via: [made1.id, up.id] },
    }),
  );
  const web = await webOf(w, 'The court', [wren.id, mara.id, tomas.id]);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/web/?tenant=${w.tenant.id}&id=${web.id}`);
  const drawing = page.getByRole('group', { name: 'The court' });
  await expect(drawing.getByRole('button', { name: 'Wren Ashdown' })).toBeVisible();
  // The type labels its line, and the one that holds through a chain is dashed.
  await expect(page.locator('.gr-svg text', { hasText: 'Parent of' })).toBeVisible();
  await expect(page.locator('.gr-svg path[stroke-dasharray]').first()).toBeAttached();

  // By hand: choose the layout, move an entry with Alt and an arrow, then give it a place by number.
  await page.getByRole('button', { name: 'Drawing' }).click();
  await page.getByLabel('Layout').selectOption('manual');
  await page.getByRole('button', { name: 'Close the panel' }).click();
  await drawing.getByRole('button', { name: 'Mara Quill' }).focus();
  await page.keyboard.press('Space');
  await expect(page.getByLabel('X', { exact: true })).toBeVisible();
  const before = Number(await page.getByLabel('X', { exact: true }).inputValue());
  await drawing.getByRole('button', { name: 'Mara Quill' }).focus();
  await page.keyboard.press('Alt+ArrowRight');
  await expect(page.getByText(/placed by hand, not saved yet/)).toBeVisible();
  await page.getByLabel('X', { exact: true }).fill(String(before + 50));
  await page.getByLabel('X', { exact: true }).press('Tab');
  await page.getByLabel('Y', { exact: true }).fill('12');
  await page.getByLabel('Y', { exact: true }).press('Tab');
  await expect(page.getByText(/placed by hand, not saved yet/)).toBeVisible();
  await page.getByRole('button', { name: 'Fit' }).click();
});
