import { expect, type Page, test } from '@playwright/test';

// The page without sign-in runs the editor against a small repository held in memory
// (core/sample.ts), so the command layer can be driven end to end in a browser.

type SampleWindow = {
  sample: {
    offline: boolean;
    writes: { id: string; field: string; value: unknown }[];
    renameElsewhere(id: string, name: string): void;
    editTextElsewhere(id: string, which: string, text: string): void;
    setStatElsewhere(id: string, statId: string, value: unknown): void;
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
  // These tests pick entries by id from a flat list; the tree has its own tests below.
  await page.getByRole('button', { name: 'A to Z' }).click();
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

// --- description and notes -------------------------------------------------------------------

const description = (page: Page) => page.getByLabel('Description', { exact: true });
const blur = async (page: Page) => page.locator('.pane-entry h2', { hasText: 'Notes' }).click();

test('the description is shown as it reads, and edited with a preview that follows the typing', async ({
  page,
}) => {
  await page.locator('[data-entry="wolf"]').click();
  await expect(description(page)).toHaveValue('Hunts in **packs**.');
  await expect(page.getByLabel('Description, as it reads').locator('strong')).toHaveText('packs');
  await description(page).fill('Hunts in *pairs*.');
  // before it is written down, the preview already shows it
  await expect(page.getByLabel('Description, as it reads').locator('em')).toHaveText('pairs');
  expect(await writes(page)).toEqual([]);
  await blur(page);
  await expect(status(page)).toHaveText('Synced');
  expect(await writes(page)).toEqual([
    { id: 'wolf-description', field: 'description', value: 'Hunts in *pairs*.' },
  ]);
});

test('an entry with no description gets one when text is written', async ({ page }) => {
  await page.locator('[data-entry="beast"]').click();
  await expect(description(page)).toHaveValue('');
  await description(page).fill('Natural creatures.');
  await blur(page);
  await expect(status(page)).toHaveText('Synced');
  await page.locator('[data-entry="wolf"]').click();
  await page.locator('[data-entry="beast"]').click();
  await expect(description(page)).toHaveValue('Natural creatures.');
});

test('with no connection a description is saved here, and sent when it is back', async ({
  page,
}) => {
  await page.locator('[data-entry="wolf"]').click();
  await palette(page, 'lose the connection');
  await description(page).fill('Offline text.');
  await blur(page);
  await expect(status(page)).toHaveText('Saved on this device');
  await palette(page, 'get the connection back');
  await expect(status(page)).toHaveText('Synced');
  expect((await writes(page)).map((w) => w.value)).toEqual(['Offline text.']);
});

test('a description changed elsewhere is a conflict', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await palette(page, 'lose the connection');
  await description(page).fill('Mine.');
  await blur(page);
  await page.evaluate(() =>
    (window as unknown as SampleWindow).sample.editTextElsewhere('wolf', 'description', 'Theirs.'),
  );
  await palette(page, 'get the connection back');
  await expect(status(page)).toHaveText('Conflict');
  await expect(page.getByRole('alert')).toContainText('Theirs.');
  await page.getByRole('button', { name: 'Keep mine' }).click();
  await expect(status(page)).toHaveText('Synced');
  await expect(description(page)).toHaveValue('Mine.');
});

test('notes are listed, added, and edited', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await expect(page.getByLabel('Note: Note', { exact: true })).toHaveValue(
    'Pairs well with a ranger.',
  );
  await page.getByLabel('A new note').fill('Check the den.');
  await page.getByRole('button', { name: 'Add note' }).click();
  await expect(page.getByLabel('Note: Note', { exact: true })).toHaveCount(2);
  await expect(status(page)).toHaveText('Synced');
  await page.getByLabel('Note: Note', { exact: true }).nth(1).fill('Check the east den.');
  await blur(page);
  await expect(status(page)).toHaveText('Synced');
  expect((await writes(page)).map((w) => [w.field, w.value])).toEqual([
    ['note.add', 'Check the den.'],
    ['note.text', 'Check the east den.'],
  ]);
});

test('a note added with no connection can be edited, then both are sent in order', async ({
  page,
}) => {
  await page.locator('[data-entry="wolf"]').click();
  await palette(page, 'lose the connection');
  await page.getByLabel('A new note').fill('Draft.');
  await page.getByRole('button', { name: 'Add note' }).click();
  await page.getByLabel('Note: Note', { exact: true }).nth(1).fill('Final.');
  await blur(page);
  await palette(page, 'get the connection back');
  await expect(status(page)).toHaveText('Synced');
  expect((await writes(page)).map((w) => [w.field, w.value])).toEqual([
    ['note.add', 'Draft.'],
    ['note.text', 'Final.'],
  ]);
});

test('what is typed in a description survives another change arriving', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await description(page).focus();
  await description(page).fill('Half a sentence');
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
  await expect(description(page)).toHaveValue('Half a sentence');
  await expect(description(page)).toBeFocused();
});

const stats = (page: Page) => page.locator('.pane-props');

test("an inherited stat is shown as inherited; writing it makes it the entry's own", async ({
  page,
}) => {
  await page.locator('[data-entry="wolf"]').click();
  const armor = stats(page).getByLabel('Armor class (inherited)');
  await expect(armor).toHaveValue('10');
  await armor.fill('13');
  await armor.press('Enter');
  await expect(stats(page).getByLabel('Armor class', { exact: true })).toHaveValue('13');
  await expect(stats(page).locator('[data-stat="armor"]')).toHaveClass(/own/);
  await expect(status(page)).toHaveText('Synced');
  expect(await writes(page)).toEqual([{ id: 'wolf', field: 'stat:armor', value: 13 }]);
});

test('removing an own value makes the entry inherit again, and undo puts it back', async ({
  page,
}) => {
  await page.locator('[data-entry="wolf"]').click();
  await stats(page).getByLabel('Armor class (inherited)').fill('13');
  await stats(page).getByLabel('Armor class (inherited)').press('Enter');
  await stats(page).getByRole('button', { name: 'Remove Armor class' }).click();
  await expect(stats(page).getByLabel('Armor class (inherited)')).toHaveValue('10');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(stats(page).getByLabel('Armor class', { exact: true })).toHaveValue('13');
  await expect(status(page)).toHaveText('Synced');
});

test('a tag is a checkbox, a stat can be added, and an enum is a choice', async ({ page }) => {
  await page.locator('[data-entry="zombie"]').click();
  await expect(stats(page).getByLabel('Undead (inherited)')).toBeChecked();
  await stats(page).getByLabel('Undead (inherited)').click();
  await expect(stats(page).getByLabel('Undead', { exact: true })).not.toBeChecked();
  await stats(page).getByLabel('Add a stat').selectOption({ label: 'Size' });
  await stats(page).getByLabel('Size', { exact: true }).selectOption('large');
  await expect(status(page)).toHaveText('Synced');
  expect(await writes(page)).toEqual([
    { id: 'zombie', field: 'stat:undead', value: false },
    { id: 'zombie', field: 'stat:size', value: 'tiny' },
    { id: 'zombie', field: 'stat:size', value: 'large' },
  ]);
});

test('a decimal stat is shown but not editable yet', async ({ page }) => {
  await page.locator('[data-entry="wolf"]').click();
  await expect(stats(page).getByLabel('Add a stat')).not.toContainText('Weight');
});

test('with no connection a stat is saved here, and a change elsewhere is a conflict', async ({
  page,
}) => {
  await page.locator('[data-entry="monster"]').click();
  await palette(page, 'lose the connection');
  await stats(page).getByLabel('Armor class', { exact: true }).fill('15');
  await stats(page).getByLabel('Armor class', { exact: true }).press('Enter');
  await expect(status(page)).toHaveText('Saved on this device');
  await page.evaluate(() =>
    (window as unknown as SampleWindow).sample.setStatElsewhere('monster', 'armor', 18),
  );
  await palette(page, 'get the connection back');
  await expect(page.getByRole('alert')).toContainText('Armor class was changed elsewhere to 18');
  await page.getByRole('button', { name: 'Keep mine' }).click();
  await expect(status(page)).toHaveText('Synced');
  expect(await writes(page)).toEqual([{ id: 'monster', field: 'stat:armor', value: 15 }]);
});

test('the LIVE banner says libraries see the edits of a published repository, and can be hidden', async ({
  page,
}) => {
  const live = page.locator('#live');
  await expect(live).toBeHidden();
  await palette(page, 'publish the repository');
  await expect(live).toContainText('Libraries that copied this repository see your edits');
  await live.getByRole('button', { name: 'Hide' }).click();
  await expect(live).toBeHidden();
});

test.describe('the explorer', () => {
  test.beforeEach(async ({ page }) => {
    // the default order, which the tests above leave
    await page.evaluate(() => localStorage.removeItem('bench:explorer-order'));
    await page.reload();
    await expect(page.getByRole('button', { name: 'Inherits' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
  const rows = (page: Page) => page.locator('.pane-explorer .place .row');

  test('is a tree of what entries inherit from, one row for each place', async ({ page }) => {
    await expect(rows(page).filter({ hasText: /^Ghoul$/ })).toHaveCount(2);
    await expect(page.locator('.pane-explorer')).toContainText(
      '11 entries · 12 places in the list',
    );
    await expect(page.getByRole('img', { name: 'Has 2 parents' })).toHaveCount(2);
  });

  test('selecting an entry marks every place it is in', async ({ page }) => {
    await rows(page)
      .filter({ hasText: /^Ghoul$/ })
      .first()
      .click();
    await expect(name(page)).toHaveValue('Ghoul');
    await expect(page.locator('.pane-explorer .row.on')).toHaveCount(2);
  });

  test('folding an entry hides what is under it, and unfolding brings it back', async ({
    page,
  }) => {
    const wolf = rows(page).filter({ hasText: /^Wolf$/ });
    await expect(wolf).toBeVisible();
    await page.getByRole('button', { name: 'Fold Monster' }).click();
    await expect(wolf).toHaveCount(0);
    await page.getByRole('button', { name: 'Unfold Monster' }).click();
    await expect(wolf).toBeVisible();
  });

  test('can be grouped by kind, and listed A to Z', async ({ page }) => {
    await page.getByRole('button', { name: 'Kind', exact: true }).click();
    await expect(page.locator('.pane-explorer .group-head')).toHaveText([
      'Items',
      'Beings',
      'Bare entries',
    ]);
    await page.getByRole('button', { name: 'A to Z' }).click();
    await expect(rows(page).first()).toHaveText('Ashfang');
    await expect(page.locator('.pane-explorer')).toContainText('11 entries');
  });

  test('the order is remembered', async ({ page }) => {
    await page.getByRole('button', { name: 'Kind', exact: true }).click();
    await page.reload();
    await expect(page.getByRole('button', { name: 'Kind', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  test('a new entry shows under its parent at once', async ({ page }) => {
    await page.getByLabel('Name of the new entry').fill('Pup');
    await page.getByLabel('Parent of the new entry').selectOption({ label: 'Wolf' });
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(rows(page).filter({ hasText: /^Pup$/ })).toHaveCount(1);
  });

  test('changing parents moves the entry in the tree', async ({ page }) => {
    await rows(page)
      .filter({ hasText: /^Zombie$/ })
      .click();
    await page.getByLabel('Add a parent').selectOption({ label: 'Beast' });
    await expect(rows(page).filter({ hasText: /^Zombie$/ })).toHaveCount(2);
  });
});

test('an entry can be an item, a being, both or neither', async ({ page }) => {
  await page.locator('[data-entry="ashfang"]').click();
  const being = page.getByRole('checkbox', { name: /Being/ });
  const item = page.getByRole('checkbox', { name: /Item/ });
  await expect(being).toBeChecked();
  await expect(item).not.toBeChecked();
  await item.check();
  await being.uncheck();
  await expect(status(page)).toHaveText('Synced');
  await expect(page.locator('.pane-entry .kind')).toHaveText('item');
  expect(await writes(page)).toEqual([
    { id: 'ashfang', field: 'kind:item', value: true },
    { id: 'ashfang', field: 'kind:being', value: false },
  ]);
  // the entry may be neither: a bare entry is what a group is
  await item.uncheck();
  await expect(page.locator('.pane-entry .kind')).toHaveText('bare entry');
});

test('a kind change is undone from the entry', async ({ page }) => {
  await page.locator('[data-entry="ashfang"]').click();
  await page.getByRole('checkbox', { name: /Item/ }).check();
  await expect(status(page)).toHaveText('Synced');
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(page.getByRole('checkbox', { name: /Item/ })).not.toBeChecked();
});
