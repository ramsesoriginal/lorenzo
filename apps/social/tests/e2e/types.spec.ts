import { expect, test } from '@playwright/test';
import { signedIn, world } from './support/world.ts';

test('an Owner adds the starter, and a relationship reads in the words of its type', async ({
  browser,
}) => {
  const w = await world();
  const mara = await w.person('Mara Quill');
  const wren = await w.person('Wren Ashdown');
  const page = await signedIn(browser, w.subject);
  await page.goto(`/types/?tenant=${w.tenant.id}`);
  await expect(page.getByRole('heading', { name: 'Types and standings', level: 1 })).toBeVisible();
  await expect(page.getByText('Start from a set of types and standings')).toBeVisible();
  await page.getByRole('button', { name: 'Add the starter' }).click();
  const types = page.getByRole('list', { name: 'Types of relationship' });
  await expect(types.getByText('Parent of', { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(
    types.getByText('Goes one way. Reads as “is the parent of / is a child of”.'),
  ).toBeVisible();
  await expect(page.getByText('Start from a set of types and standings')).toHaveCount(0);
  const standings = page.getByRole('list', { name: 'Standings' });
  await expect(standings.getByText('From -10 to 10.').first()).toBeVisible();

  // A relationship of that type reads with the library's words.
  await page.goto(`/relationships/?tenant=${w.tenant.id}`);
  const form = page.getByRole('form', { name: 'Make a relationship' });
  await form.getByLabel('First end: search by name').fill('Mara');
  await form.getByLabel('First end: results').selectOption({ label: mara.name });
  await form.getByLabel('Second end: search by name').fill('Wren');
  await form.getByLabel('Second end: results').selectOption({ label: wren.name });
  await form.getByLabel('How it goes').selectOption('one');
  await form.getByLabel('Type of relationship (optional): search by name').fill('Parent');
  await form
    .getByLabel('Type of relationship (optional): results')
    .selectOption({ label: 'Parent of' });
  await form.getByRole('button', { name: 'Make the relationship' }).click();
  await expect(page.getByText('Mara Quill is the parent of Wren Ashdown')).toBeVisible();
});

test('a standing is added with a scale, and a scale values already break is refused', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  await page.goto(`/types/?tenant=${w.tenant.id}`);
  const form = page.getByRole('form', { name: 'Add a standing' });
  await form.getByLabel('Name of the standing').fill('Trust');
  await form.getByLabel('From (optional)').fill('0');
  await form.getByLabel('To (optional)').fill('5');
  await form.getByRole('button', { name: 'Add the standing' }).click();
  const standings = page.getByRole('list', { name: 'Standings' });
  await expect(standings.getByText('From 0 to 5.')).toBeVisible();
});
