import { expect, type Page, test } from '@playwright/test';

// The page without sign-in runs the editor against a small repository held in memory
// (core/sample.ts), so the command layer can be driven end to end in a browser.

type SampleWindow = {
  sample: {
    offline: boolean;
    writes: { id: string; field: string; value: unknown }[];
    renameElsewhere(id: string, name: string): void;
  };
};

const name = (page: Page) => page.getByLabel('Name', { exact: true });
const status = (page: Page) => page.locator('.pane-entry [role="status"]');
const palette = async (page: Page, text: string) => {
  await page.keyboard.press('Control+k');
  await page.getByLabel('Command palette').fill(text);
  await page.keyboard.press('Enter');
};
const writes = (page: Page) =>
  page.evaluate(() => (window as unknown as SampleWindow).sample.writes);

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(name(page)).toHaveValue('Monster');
});

test('lists the repository and opens an entry', async ({ page }) => {
  await expect(page.locator('[data-entry]')).toHaveCount(11);
  await page.locator('[data-entry="wolf"]').click();
  await expect(name(page)).toHaveValue('Wolf');
  await expect(status(page)).toHaveText('Synced');
});

test('renaming writes it and says Synced', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await name(page).fill('Dire wolf!');
  await name(page).press('Enter');
  await expect(page.locator('[data-entry="wolf"]')).toHaveText('Dire wolf!');
  await expect(status(page)).toHaveText('Synced');
  expect(await writes(page)).toEqual([{ id: 'wolf', field: 'name', value: 'Dire wolf!' }]);
});

test('with no connection a change is saved here, and sent when it is back', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await palette(page, 'lose the connection');
  await name(page).fill('Hound');
  await name(page).press('Enter');
  await expect(status(page)).toHaveText('Saved on this device');
  await expect(page.locator('[data-entry="wolf"]')).toHaveText('Hound');
  expect(await writes(page)).toEqual([]);
  await palette(page, 'get the connection back');
  await expect(status(page)).toHaveText('Synced');
  expect(await writes(page)).toEqual([{ id: 'wolf', field: 'name', value: 'Hound' }]);
});

test('undo cancels a change that was not sent', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await palette(page, 'lose the connection');
  await name(page).fill('Hound');
  await name(page).press('Enter');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(name(page)).toHaveValue('Wolf');
  await palette(page, 'get the connection back');
  expect(await writes(page)).toEqual([]);
});

test('undo of a change that was sent sends the inverse', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await name(page).fill('Hound');
  await name(page).press('Enter');
  await expect(status(page)).toHaveText('Synced');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(name(page)).toHaveValue('Wolf');
  await expect(status(page)).toHaveText('Synced');
  expect((await writes(page)).map((w) => w.value)).toEqual(['Hound', 'Wolf']);
});

test('a change to the same name elsewhere is a conflict, resolved by keeping mine', async ({
  page,
}) => {
  await page.locator('[data-entry="wolf"]').click();
  await palette(page, 'lose the connection');
  await name(page).fill('Hound');
  await name(page).press('Enter');
  await page.evaluate(() =>
    (window as unknown as SampleWindow).sample.renameElsewhere('wolf', 'Coyote'),
  );
  await palette(page, 'get the connection back');
  await expect(status(page)).toHaveText('Conflict');
  await expect(page.getByRole('alert')).toContainText('“Coyote”');
  expect(await writes(page)).toEqual([]);
  await page.getByRole('button', { name: 'Keep mine' }).click();
  await expect(status(page)).toHaveText('Synced');
  expect(await writes(page)).toEqual([{ id: 'wolf', field: 'name', value: 'Hound' }]);
});

test('using theirs drops my change', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await palette(page, 'lose the connection');
  await name(page).fill('Hound');
  await name(page).press('Enter');
  await page.evaluate(() =>
    (window as unknown as SampleWindow).sample.renameElsewhere('wolf', 'Coyote'),
  );
  await palette(page, 'get the connection back');
  await page.getByRole('button', { name: 'Use theirs' }).click();
  await expect(name(page)).toHaveValue('Coyote');
  await expect(status(page)).toHaveText('Synced');
});

test('parents can be added and removed', async ({ page }) => {
  await page.locator('[data-entry="ghoul"]').click();
  const parents = page.locator('.pane-entry .parent');
  await expect(parents).toHaveText(['Undead×', 'Beast×']);
  await page.getByLabel('Remove parent Beast').click();
  await expect(parents).toHaveText(['Undead×']);
  await page.getByLabel('Add a parent').selectOption({ label: 'Zombie' });
  await expect(parents).toHaveText(['Undead×', 'Zombie×']);
  await expect(status(page)).toHaveText('Synced');
  const last = (await writes(page)).at(-1);
  expect(last).toMatchObject({ id: 'ghoul', field: 'parents', value: ['undead', 'zombie'] });
});

test('a refused change says why, and Discard puts the old value back', async ({ page }) => {
  await page.locator('[data-entry="ghoul"]').click();
  // The sample server refuses an item being its own parent; the menu does not offer it, so
  // the refusal is provoked through the bench itself.
  await page.evaluate(() => {
    const b = (
      window as unknown as { bench: { bench: { change(t: string, id: string, v: unknown): void } } }
    ).bench.bench;
    b.change('entry.set-parents', 'ghoul', ['ghoul']);
  });
  await expect(status(page)).toHaveText('Needs attention');
  await expect(page.getByRole('alert')).toContainText('own parent');
  await page.getByRole('button', { name: 'Discard' }).click();
  await expect(status(page)).toHaveText('Synced');
  await expect(page.locator('.pane-entry .parent')).toHaveText(['Undead×', 'Beast×']);
});

test('what is being typed survives another change arriving', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await name(page).focus();
  await name(page).fill('Half a na');
  // another entry's change redraws the page
  await page.evaluate(() => {
    const b = (
      window as unknown as {
        bench: {
          bench: {
            change(t: string, id: string, v: unknown): void;
            open(id: string): Promise<void>;
          };
        };
      }
    ).bench.bench;
    return b.open('zombie').then(() => b.change('entry.set-name', 'zombie', 'Walker'));
  });
  await expect(page.locator('[data-entry="zombie"]')).toHaveText('Walker');
  await expect(name(page)).toHaveValue('Half a na');
  await expect(name(page)).toBeFocused();
});

test('a bare entry or a being is shown with what it is; only an item can be renamed', async ({
  page,
}) => {
  await page.locator('[data-entry="hollow"]').click();
  await expect(page.locator('.pane-entry')).toContainText('bare entry');
  await expect(name(page)).toBeDisabled();
  await page.locator('[data-entry="ashfang"]').click();
  await expect(page.locator('.pane-entry')).toContainText('being');
  await expect(name(page)).toBeDisabled();
});

test('the parents of a being can be changed', async ({ page }) => {
  await page.locator('[data-entry="ashfang"]').click();
  await page.getByLabel('Add a parent').selectOption({ label: 'Wolf' });
  await expect(page.locator('.pane-entry .parent')).toHaveText(['The Hollow×', 'Wolf×']);
  await expect(status(page)).toHaveText('Synced');
});

// --- making entries --------------------------------------------------------------------------

const make = async (page: Page, text: string, kind: string, parent: string) => {
  await page.getByLabel('Name of the new entry').fill(text);
  await page.getByLabel('Kind of the new entry').selectOption({ label: kind });
  await page.getByLabel('Parent of the new entry').selectOption({ label: parent });
  await page.getByRole('button', { name: 'Add', exact: true }).click();
};

test('a new item shows at once under its parent, and is sent with its own id', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await make(page, 'Winter wolf', 'Item', 'Wolf');
  await expect(name(page)).toHaveValue('Winter wolf');
  await expect(page.locator('[data-entry]', { hasText: 'Winter wolf' })).toBeVisible();
  await expect(status(page)).toHaveText('Synced');
  await expect(page.locator('.pane-entry .parent')).toHaveText(['Wolf×']);
  const writes = await page.evaluate(() => (window as unknown as SampleWindow).sample.writes);
  expect(writes).toEqual([
    { id: expect.stringMatching(/^[0-9a-f-]{36}$/), field: 'create', value: 'Winter wolf' },
  ]);
  // and the parent lists it as a child
  await page.locator('[data-entry="wolf"]').click();
  await page.getByRole('tab', { name: 'Parents and children' }).click();
  await expect(page.locator('.pane-links')).toContainText('Winter wolf');
});

test('with no connection a new entry is saved here, edited, and all of it sent in order', async ({
  page,
}) => {
  await palette(page, 'lose the connection');
  await make(page, 'Frost giant', 'Being', 'No parent');
  await expect(status(page)).toHaveText('Saved on this device');
  await expect(page.locator('.pane-entry')).toContainText('being');
  await page.getByLabel('Add a parent').selectOption({ label: 'Monster' });
  await expect(page.locator('.pane-entry .parent')).toHaveText(['Monster×']);
  expect(await writes(page)).toEqual([]);
  await palette(page, 'get the connection back');
  await expect(status(page)).toHaveText('Synced');
  expect((await writes(page)).map((w) => w.field)).toEqual(['create', 'parents']);
});

test('an entry made under one that is not sent yet goes after it', async ({ page }) => {
  await palette(page, 'lose the connection');
  await make(page, 'Pack', 'Item', 'No parent');
  await make(page, 'Pup', 'Item', 'Pack');
  await palette(page, 'get the connection back');
  await expect(status(page)).toHaveText('Synced');
  expect((await writes(page)).map((w) => w.value)).toEqual(['Pack', 'Pup']);
});

test('undo of a new entry that was not sent takes it away', async ({ page }) => {
  await palette(page, 'lose the connection');
  await make(page, 'Mistake', 'Item', 'No parent');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(page.locator('[data-entry]', { hasText: 'Mistake' })).toHaveCount(0);
  await palette(page, 'get the connection back');
  expect(await writes(page)).toEqual([]);
});

test('a new entry that was sent cannot be undone here', async ({ page }) => {
  await make(page, 'Kept', 'Item', 'No parent');
  await expect(status(page)).toHaveText('Synced');
  await expect(page.getByRole('button', { name: 'Undo' })).toBeDisabled();
});
