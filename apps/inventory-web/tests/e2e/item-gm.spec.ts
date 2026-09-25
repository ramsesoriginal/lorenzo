import type { Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import type { World } from './support/world.ts';

async function gmOn(as: (who: World['gm']) => Promise<Page>, world: World, id: string) {
  const page = await as(world.gm);
  await page.goto(`/item/?tenant=${world.tenantId}&id=${id}`);
  return page;
}

async function nameOf(world: World, id: string) {
  const entity = await ok(
    world.gm.api.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: world.tenantId, entity_id: id } },
    }),
  );
  return entity.name;
}

test('writes a description with a display title, keeping the name', async ({ world, as }) => {
  const lantern = await world.item('Lantern');
  const page = await gmOn(as, world, lantern);

  await page.getByRole('button', { name: 'Write a description' }).click();
  await expect(page.getByLabel('Display title')).toHaveValue('Lantern');
  await page.getByLabel('Display title').fill('Hooded Lantern');
  await page.getByRole('textbox', { name: 'Description' }).fill('Shutters on *three* sides.');
  await page.getByRole('button', { name: 'Save' }).click();

  await expect(page.getByRole('heading', { level: 1, name: 'Hooded Lantern' })).toBeVisible();
  await expect(page.locator('#item-view').getByText('Shutters on three sides.')).toBeVisible();
  expect(await nameOf(world, lantern)).toBe('Lantern');

  await page.getByRole('button', { name: 'Edit description' }).click();
  await expect(page.getByRole('textbox', { name: 'Description' })).toHaveValue(
    'Shutters on *three* sides.',
  );
  await page.getByRole('textbox', { name: 'Description' }).fill('Shutters on four sides.');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.locator('#item-view').getByText('Shutters on four sides.')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Hooded Lantern' })).toBeVisible();
});

test('a description only its GMs may read stays hidden from players', async ({ world, as }) => {
  const lantern = await world.item('Lantern');
  const mine = await world.instance(lantern, { owner: world.pia });
  const page = await gmOn(as, world, mine);

  await page.getByRole('button', { name: 'Write a description' }).click();
  await page.getByRole('textbox', { name: 'Description' }).fill('Its flame is a bound spirit.');
  await page.getByLabel('Players can read this').uncheck();
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.locator('#item-view').getByText('Its flame is a bound spirit.')).toBeVisible();

  const pia = await as(world.pia);
  await pia.goto(`/item/?tenant=${world.tenantId}&id=${mine}`);
  await expect(pia.getByRole('heading', { level: 1, name: 'Lantern' })).toBeVisible();
  await expect(pia.getByText('Its flame is a bound spirit.')).toBeHidden();
});

test('sets a tag on, off, and back to what it inherits', async ({ world, as }) => {
  const stick = await world.item('Stick', { tags: ['is_magical'] });
  const wand = await world.item('Wand', { prototypes: [stick] });
  const page = await gmOn(as, world, wand);
  const magical = page
    .getByRole('region', { name: 'Tags' })
    .getByRole('group', { name: 'Magical' });
  const chip = page.locator('.item-view').getByRole('listitem').filter({ hasText: 'Magical' });

  await expect(magical.getByLabel('Inherited (on)')).toBeChecked();
  await expect(chip).toBeVisible();
  await magical.getByLabel('Off').check();
  await expect(chip).toBeHidden();
  await expect(magical.getByLabel('Off')).toBeChecked();
  await magical.getByLabel(/^Inherited/).check();
  await expect(chip).toBeVisible();

  const cursed = page.getByRole('region', { name: 'Tags' }).getByRole('group', { name: 'Cursed' });
  await cursed.getByLabel('On').check();
  await expect(
    page.locator('.item-view').getByRole('listitem').filter({ hasText: 'Cursed' }),
  ).toBeVisible();
});

test('adds, edits, and deletes information', async ({ world, as }) => {
  const lantern = await world.item('Lantern', { description: 'A plain lantern.' });
  const page = await gmOn(as, world, lantern);
  const information = page.getByRole('region', { name: 'Information' });

  // The description is one piece of information among them.
  await expect(information.getByText('description · Players can read this')).toBeVisible();

  await information.getByRole('button', { name: 'Add information' }).click();
  await information.getByLabel('Title').fill('Rumour');
  await information.getByLabel('Type').fill('rumour');
  await information.getByRole('textbox', { name: 'Text' }).fill('Stolen from a lighthouse.');
  await information.getByRole('button', { name: 'Save' }).click();
  const rumour = information.getByRole('listitem').filter({ hasText: 'Stolen from a lighthouse.' });
  await expect(rumour.getByRole('heading', { name: 'Rumour' })).toBeVisible();
  await expect(rumour.getByText('rumour · Private')).toBeVisible();

  await rumour.getByRole('button', { name: 'Edit' }).click();
  await information.getByLabel('Title').fill('Old rumour');
  await information.getByLabel('Players can read this').check();
  await information.getByRole('button', { name: 'Save' }).click();
  const edited = information.getByRole('listitem').filter({ hasText: 'Old rumour' });
  await expect(edited.getByText('rumour · Players can read this')).toBeVisible();

  page.once('dialog', (dialog) => dialog.accept());
  await edited.getByRole('button', { name: 'Delete' }).click();
  await expect(information.getByText('Old rumour')).toBeHidden();
  await expect(information.getByText('description · Players can read this')).toBeVisible();
});

test('says why a second description is refused', async ({ world, as }) => {
  const lantern = await world.item('Lantern', { description: 'A plain lantern.' });
  const page = await gmOn(as, world, lantern);
  const information = page.getByRole('region', { name: 'Information' });

  await information.getByRole('button', { name: 'Add information' }).click();
  await information.getByLabel('Title').fill('Another');
  await information.getByLabel('Type').fill('description');
  await information.getByRole('textbox', { name: 'Text' }).fill('A second one.');
  await information.getByRole('button', { name: 'Save' }).click();
  await expect(information.getByRole('status').filter({ hasText: /description/i })).toBeVisible();
});
