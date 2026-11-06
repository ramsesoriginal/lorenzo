import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { signedIn, world } from './support/world.ts';

test('a GM makes a relationship from the form and reads it on its page', async ({ browser }) => {
  const w = await world();
  await w.entry('Mara Quill');
  await w.entry('Wren Ashdown');
  const page = await signedIn(browser, w.subject);
  await page.goto('/');
  await page.getByRole('link', { name: w.tenant.name }).click();
  await expect(page.getByRole('heading', { name: 'Relationships', level: 1 })).toBeVisible();
  await expect(page.getByText('There are no relationships you can see yet.')).toBeVisible();

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
  const wren = await w.entry('Wren Ashdown');
  const page = await signedIn(browser, w.playerSubject);
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
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
  page.once('dialog', (dialog) => void dialog.accept());
  await page.getByRole('button', { name: 'Delete it' }).click();
  await expect(page.getByRole('heading', { name: 'Relationships', level: 1 })).toBeVisible();
  await expect(page.getByText('There are no relationships you can see yet.')).toBeVisible();
  expect(alice.entity_id).toBeTruthy();
});
