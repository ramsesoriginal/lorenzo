import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { ok } from './support/api.ts';
import { signedIn, standing, world } from './support/world.ts';

test('a GM makes a relationship from the form and reads it on its page', async ({ browser }) => {
  const w = await world();
  await w.person('Mara Quill');
  await w.person('Wren Ashdown');
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  await expect(page.getByRole('heading', { name: 'Relationships', level: 1 })).toBeVisible();
  await expect(page.getByText('There are no relationships you can see yet.')).toBeVisible();

  await page.getByRole('button', { name: 'New relationship' }).first().click();
  const form = page.getByRole('form', { name: 'Make a relationship' });
  await form.getByLabel('First end: search by name').fill('Mara');
  await form.getByLabel('First end: results').selectOption({ label: 'Mara Quill' });
  await form.getByLabel('Second end: search by name').fill('Wren');
  await form.getByLabel('Second end: results').selectOption({ label: 'Wren Ashdown' });
  await form.getByLabel('How it goes').selectOption('one');
  await form.getByLabel('Name (optional)').fill('Mara is the parent of Wren');
  await form.getByRole('button', { name: 'Make the relationship' }).click();

  await expect(
    page.getByRole('heading', { name: 'Mara is the parent of Wren', level: 1 }),
  ).toBeVisible();
  await expect(page.getByText('From Mara Quill to Wren Ashdown').first()).toBeVisible();
  await expect(page.getByText('Restricted')).toBeVisible();

  // Opening it to the library, then swapping the ends, change what the page says.
  await page.getByRole('button', { name: 'Let everyone in the library see it' }).click();
  await expect(page.getByText('Everyone in the library')).toBeVisible();
  await page.getByRole('button', { name: 'Swap the two ends' }).click();
  await expect(page.getByText('From Wren Ashdown to Mara Quill').first()).toBeVisible();
});

test('a player sees only the relationships they may, and a form with no way to open one up', async ({
  browser,
}) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  const hidden = await w.entry('The sealed vault', false);
  await w.tie('Open friendship', a.id, b.id, true);
  await w.tie('Secret oath', a.id, b.id, false);
  await w.tie('Cut tie', a.id, hidden.id, true);
  const page = await signedIn(browser, w.playerSubject);
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  await expect(page.getByRole('link', { name: 'Open friendship' })).toBeVisible();
  await expect(page.getByText('Showing 1 of 1.')).toBeVisible();
  await expect(page.getByText('Secret oath')).toHaveCount(0);
  await expect(page.getByText('Cut tie')).toHaveCount(0);
  await expect(page.getByText('sealed vault')).toHaveCount(0);
  // The form is offered, without the choice of opening it to everyone (ADR 0425).
  await page.getByRole('button', { name: 'New relationship' }).first().click();
  await expect(page.getByRole('form', { name: 'Make a relationship' })).toBeVisible();
  await expect(page.getByLabel('Everyone in the library may see it')).toHaveCount(0);
});

for (const theme of ['light', 'dark'] as const) {
  test(`the list and the page have no axe violations in ${theme}`, async ({ browser }) => {
    const w = await world();
    const a = await w.entry('Mara Quill');
    const b = await w.entry('Wren Ashdown');
    const made = await w.tie('Open friendship', a.id, b.id, true);
    const page = await signedIn(browser, w.subject, theme);
    await page.goto(`/relationships/?tenant=${w.tenant.id}`);
    await expect(page.getByRole('link', { name: 'Open friendship' })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.goto(`/relationship/?tenant=${w.tenant.id}&id=${made.id}`);
    await expect(page.getByRole('heading', { name: 'Open friendship', level: 1 })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });
}

test('on a phone the list is one column and does not scroll sideways', async ({ browser }) => {
  const w = await world();
  const a = await w.entry('Mara Quill');
  const b = await w.entry('Wren Ashdown');
  await w.tie(
    'A very long name for a relationship between two people of the court',
    a.id,
    b.id,
    true,
  );
  const page = await signedIn(browser, w.subject);
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  await expect(page.getByRole('link', { name: /A very long name/ })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test('a player makes a relationship with their own being, and changes and deletes it', async ({
  browser,
}) => {
  const w = await world();
  const alice = await w.being('Alice the Bold');
  const wren = await w.being('Wren Ashdown');
  const page = await signedIn(browser, w.playerSubject);
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  await page.getByRole('button', { name: 'New relationship' }).first().click();
  const form = page.getByRole('form', { name: 'Make a relationship' });
  await form.getByLabel('First end: search by name').fill('Alice');
  await form.getByLabel('First end: results').selectOption({ label: 'Alice the Bold' });
  await form.getByLabel('Second end: search by name').fill('Wren');
  await form.getByLabel('Second end: results').selectOption({ label: wren.name });
  await form.getByLabel('Name (optional)').fill('Alice trusts Wren');
  await form.getByRole('button', { name: 'Make the relationship' }).click();
  await expect(page.getByRole('heading', { name: 'Alice trusts Wren', level: 1 })).toBeVisible();
  // Theirs to change, not to open up to everyone.
  await expect(page.getByRole('button', { name: 'Swap the two ends' })).toBeVisible();
  await expect(
    page.getByRole('button', { name: /Let everyone in the library see it/ }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: 'Make it go one way' }).click();
  await expect(page.getByText('From Alice the Bold to Wren Ashdown').first()).toBeVisible();
  await page.getByRole('button', { name: 'Delete it' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete it' }).click();
  await expect(page.getByRole('heading', { name: 'Relationships', level: 1 })).toBeVisible();
  await expect(page.getByText('There are no relationships you can see yet.')).toBeVisible();
  expect(alice.entity_id).toBeTruthy();
});

test('the ends offered are beings and groups, and the types offered are types', async ({
  browser,
}) => {
  const w = await world();
  const mara = await w.person('Mara Quill');
  await w.group('The Court', mara.id);
  await w.entry('The Court Hall');
  await w.entry('Ash Hold');
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  await page.getByRole('button', { name: 'New relationship' }).first().click();
  const form = page.getByRole('form', { name: 'Make a relationship' });

  // A being and a group are found; a Location is not, even when its name matches.
  await form.getByLabel('First end: search by name').fill('Mara');
  await expect(form.getByLabel('First end: results').getByRole('option')).toHaveText([
    'Mara Quill',
  ]);
  // The only option can be chosen by clicking it, as a person does.
  await form.getByLabel('First end: results').getByRole('option', { name: 'Mara Quill' }).click();
  await expect(form.getByText('Chosen: Mara Quill')).toBeVisible();
  await form.getByLabel('Second end: search by name').fill('Court');
  await expect(form.getByLabel('Second end: results').getByRole('option')).toHaveText([
    'The Court',
  ]);
  await form.getByLabel('Second end: search by name').fill('Ash');
  await expect(form.getByText('No being or group by that name.')).toBeVisible();

  // An entry nothing makes a type of is not offered as a type.
  await form.getByLabel('Type of relationship (optional): search by name').fill('Court');
  await expect(form.getByText('No type of relationship by that name.')).toBeVisible();
});

test('the list is narrowed by a type and by an end, and the filters are cleared', async ({
  browser,
}) => {
  const w = await world();
  const mara = await w.person('Mara Quill');
  const wren = await w.person('Wren Ashdown');
  const dren = await w.person('Dren Holloway');
  const group = await w.group('The Court', mara.id);
  await w.tie('Mara knows Wren', mara.id, wren.id, true);
  await w.tie('Dren knows Wren', dren.id, wren.id, true);
  await w.tie('The Court holds Dren', group.id, dren.id, true);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  const list = page.getByRole('list', { name: 'Relationships' });
  await expect(list.getByRole('listitem')).toHaveCount(3);

  // By an end: a being, or a group.
  const form = page.getByRole('form', { name: 'Find relationships' });
  await form.getByLabel('With the entry or group: search by name').fill('Wren');
  await form.getByLabel('With the entry or group: results').selectOption({ label: 'Wren Ashdown' });
  await form.getByRole('button', { name: 'Find', exact: true }).click();
  await expect(list.getByRole('listitem')).toHaveCount(2);
  await expect(list.getByText('The Court holds Dren')).toHaveCount(0);

  await form.getByLabel('With the entry or group: search by name').fill('Court');
  await form.getByLabel('With the entry or group: results').selectOption({ label: 'The Court' });
  await form.getByRole('button', { name: 'Find', exact: true }).click();
  await expect(list.getByRole('listitem')).toHaveCount(1);
  await expect(list.getByRole('link', { name: 'The Court holds Dren' })).toBeVisible();

  await form.getByRole('button', { name: 'Clear the filters' }).click();
  await expect(list.getByRole('listitem')).toHaveCount(3);
});

test('a relationship is tied to an Event and holds through a chain, and swapping its ends keeps its time', async ({
  browser,
}) => {
  const w = await world();
  const wren = await w.entry('Wren Ashdown');
  const mara = await w.entry('Mara Quill');
  const tomas = await w.entry('Tomas Ashdown');
  await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'The wedding', kinds: ['event'], parents: [] },
    }),
  );
  const grand = await w.tie('Wren and Tomas', wren.id, tomas.id, true);
  await w.tie('Wren and Mara', wren.id, mara.id, true);
  await w.tie('Mara and Tomas', mara.id, tomas.id, true);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationship/?tenant=${w.tenant.id}&id=${grand.id}`);
  await expect(page.getByText('It is not tied to any Event.')).toBeVisible();

  // No web names it yet.
  await expect(page.getByText('No web you can see has both of its ends.')).toBeVisible();
  await page.getByLabel('Since this Event: search by name').fill('wedding');
  await page.getByLabel('Since this Event: results').selectOption({ label: 'The wedding' });
  await page.getByRole('button', { name: 'Set since' }).click();
  await expect(page.getByText('Since The wedding.')).toBeVisible();

  // Swapping the ends does not clear the time (the API replaces it with the rest).
  await page.getByRole('button', { name: 'Swap the two ends' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page.getByText('Since The wedding.')).toBeVisible();

  // The chain it is stated to hold through: added, read in order, and taken out.
  for (const step of ['Wren and Mara', 'Mara and Tomas']) {
    // The page may still be drawing itself after the last change: fill and choose again until it holds.
    await expect(async () => {
      await page.getByLabel('Add a step: search by name').fill(step);
      await page.getByLabel('Add a step: results').selectOption({ label: step }, { timeout: 2000 });
    }).toPass({ timeout: 15_000 });
    await page.getByRole('button', { name: 'Add it to the chain' }).click();
    await expect(
      page
        .getByRole('list', { name: 'The chain it holds through' })
        .getByRole('link', { name: step }),
    ).toBeVisible();
  }
  await page.getByRole('button', { name: 'Take out Wren and Mara' }).click();
  await expect(
    page
      .getByRole('list', { name: 'The chain it holds through' })
      .getByRole('link', { name: 'Wren and Mara' }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: 'Clear since' }).click();
  await expect(page.getByText('It is not tied to any Event.')).toBeVisible();
});

test('the list is narrowed by a standing and the numbers it lies between', async ({ browser }) => {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const mara = await w.entry('Mara Quill');
  const wren = await w.entry('Wren Ashdown');
  const dren = await w.entry('Dren Holloway');
  const low = await w.tie('Cold with each other', mara.id, wren.id, true);
  const high = await w.tie('Warm with each other', wren.id, dren.id, true);
  await w.tie('Valueless', mara.id, dren.id, true);
  for (const [tie, value] of [
    [low.id, 2],
    [high.id, 8],
  ] as const) {
    await ok(
      w.gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
        params: { path: { ...w.path, entity_id: tie, stat_definition_id: honor.id } },
        body: { value, acquire_group: true },
      }),
    );
  }
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  const list = page.getByRole('list', { name: 'Relationships' });
  await expect(list.getByRole('listitem')).toHaveCount(3);
  const form = page.getByRole('form', { name: 'Find relationships' });
  await form.getByLabel('Having the standing').selectOption(honor.id);
  await form.getByRole('button', { name: 'Find', exact: true }).click();
  await expect(list.getByRole('listitem')).toHaveCount(2);
  await form.getByLabel('At least').fill('5');
  await form.getByRole('button', { name: 'Find', exact: true }).click();
  await expect(list.getByRole('listitem')).toHaveCount(1);
  await expect(list.getByRole('link', { name: 'Warm with each other' })).toBeVisible();
  await form.getByLabel('At least').fill('');
  await form.getByLabel('At most').fill('5');
  await form.getByRole('button', { name: 'Find', exact: true }).click();
  await expect(list.getByRole('link', { name: 'Cold with each other' })).toBeVisible();
  await expect(list.getByRole('listitem')).toHaveCount(1);
});

test('a relationship page lists the webs that have both of its ends', async ({ browser }) => {
  const w = await world();
  const wren = await w.entry('Wren Ashdown');
  const mara = await w.entry('Mara Quill');
  const tie = await w.tie('Wren and Mara', wren.id, mara.id, true);
  const made = await ok(
    w.gm.POST('/tenants/{tenant_id}/social-webs', {
      params: { path: w.path },
      body: { name: 'The court', is_public: true, layout: 'circle', layout_seed: 1 },
    }),
  );
  const read = await w.gm.GET('/tenants/{tenant_id}/social-webs/{web_id}', {
    params: { path: { ...w.path, web_id: made.id } },
  });
  await ok(
    w.gm.POST('/tenants/{tenant_id}/social-webs/{web_id}/members/bulk', {
      params: { path: { ...w.path, web_id: made.id } },
      headers: { 'If-Match': read.response.headers.get('etag') ?? '' },
      body: { set: [wren.id, mara.id].map((entry_id) => ({ entry_id })) },
    }),
  );
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationship/?tenant=${w.tenant.id}&id=${tie.id}`);
  await expect(
    page
      .getByRole('list', { name: 'The webs that name it' })
      .getByRole('link', { name: 'The court' }),
  ).toBeVisible();
});

test('every standing of the library is read on a relationship, and one with no value is set where it is read', async ({
  browser,
}) => {
  const w = await world();
  await standing(w, 'Honor', { min: -10, max: 10 });
  await standing(w, 'Faith');
  const mara = await w.entry('Mara Quill');
  const wren = await w.entry('Wren Ashdown');
  const tie = await w.tie('Mara knows Wren', mara.id, wren.id, true);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationship/?tenant=${w.tenant.id}&id=${tie.id}`);
  const rows = page.getByRole('list', { name: 'Standings of this relationship' });
  await expect(rows.getByText('Scale -10 to 10. No value.')).toBeVisible();
  await expect(
    rows.getByText('No scale set; shaded across the visible range. No value.'),
  ).toBeVisible();

  // Setting one that has no value yet; refused outside its scale; Undo takes it away again.
  const honor = page.getByLabel('Honor of Mara knows Wren');
  await honor.fill('40');
  await honor.press('Tab');
  await expect(page.getByText('40 is above the scale (up to 10).')).toBeVisible();
  await honor.fill('7');
  await honor.press('Tab');
  await expect(page.getByText('Honor of Mara knows Wren is 7')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Honor of Mara knows Wren')).toHaveValue('7');
  await page.getByLabel('Honor of Mara knows Wren').fill('3');
  await page.getByLabel('Honor of Mara knows Wren').press('Tab');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(page.getByLabel('Honor of Mara knows Wren')).toHaveValue('7');
});

test('a row of the list says its type and its standing', async ({ browser }) => {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const mara = await w.entry('Mara Quill');
  const wren = await w.entry('Wren Ashdown');
  const parent = await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'Parent of', kinds: [], parents: [] },
    }),
  );
  const tie = await ok(
    w.gm.POST('/tenants/{tenant_id}/relationships', {
      params: { path: w.path },
      body: {
        name: 'Mara is the parent of Wren',
        end_a: mara.id,
        end_b: wren.id,
        one_way: true,
        is_public: true,
        prototypes: [parent.id],
      },
    }),
  );
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: { path: { ...w.path, entity_id: tie.id, stat_definition_id: honor.id } },
      body: { value: 4, acquire_group: true },
    }),
  );
  const page = await signedIn(browser, w.subject);
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  const row = page
    .getByRole('list', { name: 'Relationships' })
    .getByRole('listitem')
    .filter({ hasText: 'Mara is the parent of Wren' });
  await expect(row.getByText('Parent of', { exact: true })).toBeVisible();
  await expect(row.locator('.standing-num')).toHaveText('4');
});
