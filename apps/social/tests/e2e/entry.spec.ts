import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { signedIn, standing, world } from './support/world.ts';

test('an entry’s page groups its relationships, sets a standing in place and lists a group’s members', async ({
  browser,
}) => {
  const w = await world();
  const honor = await standing(w, 'Honor', { min: -10, max: 10 });
  const mara = await w.person('Mara Quill');
  const wren = await w.person('Wren Ashdown');
  const dren = await w.person('Dren Holloway');
  const group = await w.group('The Court', mara.id);
  await w.tie('Mara is the parent of Wren', mara.id, wren.id, true);
  await w.tie('Dren knows Mara', dren.id, mara.id, true);
  const page = await signedIn(browser, w.subject);
  await page.goto(`/entry/?tenant=${w.tenant.id}&id=${mara.id}`);
  await expect(page.getByRole('heading', { name: 'Mara Quill', level: 1 })).toBeVisible();
  const list = page.getByRole('list', { name: 'Without a type' });
  await expect(list.getByRole('link', { name: 'Wren Ashdown' })).toBeVisible();
  await expect(list.getByRole('link', { name: 'Dren Holloway' })).toBeVisible();

  // A standing is written where it is read, inside its scale.
  await page.getByRole('combobox', { name: /^Standing/ }).selectOption(honor.id);
  const input = page.getByLabel('Honor of Mara is the parent of Wren');
  await input.fill('11');
  await input.press('Tab');
  await expect(page.getByText('11 is above the scale (up to 10).')).toBeVisible();
  await input.fill('6');
  await input.press('Tab');
  await expect(page.getByText('Saved Honor of Mara is the parent of Wren.')).toBeVisible();
  await page.reload();
  await page.getByRole('combobox', { name: /^Standing/ }).selectOption(honor.id);
  await expect(page.getByLabel('Honor of Mara is the parent of Wren')).toHaveValue('6');

  // A relationship can be made from here, with this entry as its first end.
  await page.getByRole('button', { name: 'New relationship' }).click();
  const made = page.getByRole('form', { name: 'Make a relationship' });
  await expect(made.getByText('Chosen: Mara Quill')).toBeVisible();
  await made.getByRole('button', { name: 'Cancel' }).click();

  // A group's members are apart from its relationships.
  await page.goto(`/entry/?tenant=${w.tenant.id}&id=${group.id}`);
  await expect(
    page.getByRole('list', { name: 'Members' }).getByRole('link', { name: 'Mara Quill' }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

  // It is reached from a relationship and from the web's panel.
  await page.goto(`/entry/?tenant=${w.tenant.id}&id=${wren.id}`);
  await page.getByRole('link', { name: 'Mara Quill' }).click();
  await expect(page.getByRole('heading', { name: 'Mara Quill', level: 1 })).toBeVisible();
});
