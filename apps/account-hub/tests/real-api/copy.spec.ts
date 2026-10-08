import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addItem,
  addStatGroup,
  holdings,
  invite,
  newLibrary,
  newRepository,
  newUser,
  publish,
  signedInPage,
} from './support';

// A library and a published repository it is invited to, all through the API. The repository holds
// two items and a stat group with a stat. Names carry a tag: a repository's slug is unique, and the
// tests share a database.
async function copyWorld(options: { clashing?: boolean } = {}) {
  const owner = await newUser('copier', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const library = await newLibrary(owner.api, `Table ${tag}`);
  const repository = await newRepository(owner.api, `Core ${tag}`);

  await addItem(owner.api, repository.id, 'Longsword', 'longsword');
  await addItem(owner.api, repository.id, 'Shield');
  await addStatGroup(owner.api, repository.id, 'Combat', ['Damage', 'Reach']);
  await publish(owner.api, repository.id);
  await invite(owner.api, repository.id, library.id);

  if (options.clashing) {
    // The library already has a stat group and a stat by those names, and a link name.
    await addStatGroup(owner.api, library.id, 'Combat', ['Damage']);
    await addItem(owner.api, library.id, 'My sword', 'longsword');
  }

  return { owner, tag, library, repository };
}

function wizardAddress(library: { slug: string }, repository: { id: string }, copy = 'new') {
  return `/repositories/?tenant=${library.slug}&repository=${repository.id}&copy=${copy}`;
}

function clash(page: Page, about: string) {
  return page.locator('fieldset.clash').filter({ hasText: about });
}

const step = (page: Page) => page.locator('[data-copy-step]');

test('a library copies a repository: check first, review, done', async ({ browser }) => {
  const { owner, library, repository } = await copyWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  // From the repository's page, a plain link.
  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}`);
  await page.getByRole('link', { name: 'Copy this repository' }).click();
  await expect(page).toHaveURL(/copy=new/);
  await expect(page.getByRole('heading', { name: `Copy ${repository.name}` })).toBeVisible();

  // Step 1: the limits are said before anything else, and what it brings is counted.
  await expect(step(page)).toHaveText('Step 1 of 3: Check first');
  await expect(page.getByText('cannot be undone as a whole')).toBeVisible();
  await expect(page.getByText('one game system at a time')).toBeVisible();
  await expect(page.getByText('stay GM only')).toBeVisible();
  await expect(page.locator('[data-brings]')).toContainText(
    `${repository.name}: 2 entries, 1 stat group, 2 stats`,
  );
  await expect(page.getByText('It clashes with no name in your library.')).toBeVisible();
  await page.getByRole('button', { name: 'Continue' }).click();

  // Step 2: the receipt of a copy that was made and rolled back. Nothing has changed.
  await expect(step(page)).toHaveText('Step 2 of 3: Review');
  await expect(page.locator('[data-receipt]')).toHaveText(
    'Would add 2 entries, 1 stat group and 2 stats. Nothing has changed yet.',
  );
  expect(await holdings(owner.api, library.id)).toEqual({ items: 0, statGroups: 0 });

  // Step 3: done, and now it is there.
  await page.getByRole('button', { name: 'Copy now' }).click();
  await expect(step(page)).toHaveText('Step 3 of 3: Done');
  await expect(page.locator('[data-done-receipt]')).toHaveText(
    'Added 2 entries, 1 stat group and 2 stats.',
  );
  expect(await holdings(owner.api, library.id)).toEqual({ items: 2, statGroups: 1 });

  // The link goes to the repository, which now says it is copied and offers only to copy again.
  await page.getByRole('link', { name: 'Open the repository' }).click();
  await expect(page).not.toHaveURL(/copy=/);
  await expect(
    page.getByText('Your library has copied this repository, and nothing newer'),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: 'Copy this repository' })).toHaveCount(0);
  await context.close();
});

test('name clashes: one card each, the recommended choice, and do what is recommended for all', async ({
  browser,
}) => {
  const { owner, library, repository } = await copyWorld({ clashing: true });
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(wizardAddress(library, repository));
  await expect(
    page.getByText('3 names clash with your library, and are not counted above.'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Continue' }).click();

  await expect(step(page)).toHaveText('Step 2 of 4: Name clashes');
  await expect(page.locator('fieldset.clash')).toHaveCount(3);
  await expect(
    page.getByText('Your library already has a stat group called “Combat”.'),
  ).toBeVisible();
  await expect(page.getByText('Your library already has a stat called “Damage”.')).toBeVisible();
  await expect(
    page.getByText('Your library already has an entry with the link name “longsword”.'),
  ).toBeVisible();
  // What leaving out costs, and what a new link name does to links, is said next to the choice.
  await expect(
    page.getByText('nor are its stats or any value or formula that uses them'),
  ).toBeVisible();
  await expect(page.getByText('will point at your own entry, not at this one')).toBeVisible();

  // Nothing is chosen for anyone, and so nothing goes on yet.
  await expect(page.getByText('0 of 3 settled.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Review the copy' })).toBeDisabled();

  await page.getByRole('button', { name: 'Do what is recommended for all' }).click();
  await expect(page.getByText('All 3 settled.')).toBeVisible();
  await expect(
    clash(page, 'stat group called “Combat”').getByRole('radio', { name: /Use the existing one/ }),
  ).toBeChecked();
  await expect(
    clash(page, 'stat called “Damage”').getByRole('radio', { name: /Use the existing one/ }),
  ).toBeChecked();
  const slugCard = clash(page, 'link name “longsword”');

  await expect(slugCard.getByRole('radio', { name: /Keep both/ })).toBeChecked();
  await expect(slugCard.getByLabel('New link name')).toHaveValue('longsword-2');

  await page.getByRole('button', { name: 'Review the copy' }).click();
  await expect(step(page)).toHaveText('Step 3 of 4: Review');
  await expect(page.locator('[data-receipt]')).toContainText(
    'use 1 existing stat group, use 1 existing stat, keep both of 1. Nothing has changed yet.',
  );

  await page.getByRole('button', { name: 'Copy now' }).click();
  await expect(step(page)).toHaveText('Step 4 of 4: Done');

  // The library's own stat group was used, not doubled; the copied entry has the new link name.
  expect(await holdings(owner.api, library.id)).toEqual({ items: 3, statGroups: 1 });
  const entry = await ok(
    owner.api.GET('/tenants/{tenant_id}/entities/by-slug/{slug}', {
      params: { path: { tenant_id: library.id, slug: 'longsword-2' } },
    }),
  );

  expect(entry.name).toBe('Longsword');
  await context.close();
});

test('each of the three choices, and a new name that is checked before it is sent', async ({
  browser,
}) => {
  const { owner, library, repository } = await copyWorld({ clashing: true });
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(wizardAddress(library, repository));
  await page.getByRole('button', { name: 'Continue' }).click();

  const group = clash(page, 'stat group called “Combat”');
  const stat = clash(page, 'stat called “Damage”');
  const slug = clash(page, 'link name “longsword”');

  await group.getByRole('radio', { name: /Use the existing one/ }).check();
  await slug.getByRole('radio', { name: /Leave it out/ }).check();
  await stat.getByRole('radio', { name: /Keep both/ }).check();

  // A name that is the same as the one it clashes with is no choice, and is said so.
  await stat.getByLabel('New name').fill('Damage');
  await expect(stat.getByText('Type a name that is different.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Review the copy' })).toBeDisabled();
  await stat.getByLabel('New name').fill('Damage (core)');
  await expect(stat.getByText('Type a name that is different.')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Review the copy' })).toBeEnabled();

  await page.getByRole('button', { name: 'Review the copy' }).click();
  await expect(page.locator('[data-receipt]')).toContainText(
    'use 1 existing stat group, keep both of 1, leave out 1.',
  );

  // Back keeps what was chosen.
  await page.getByRole('button', { name: 'Back' }).click();
  await expect(step(page)).toHaveText('Step 2 of 4: Name clashes');
  await expect(stat.getByLabel('New name')).toHaveValue('Damage (core)');
  await page.getByRole('button', { name: 'Review the copy' }).click();
  await page.getByRole('button', { name: 'Copy now' }).click();
  await expect(page.locator('[data-done-receipt]')).toContainText('left out 1.');

  // The entry came without its link name; the stat came under its new name beside the old one.
  expect(await holdings(owner.api, library.id)).toEqual({ items: 3, statGroups: 1 });
  const definitions = await ok(
    owner.api.GET('/tenants/{tenant_id}/stat-definitions', {
      params: { path: { tenant_id: library.id } },
    }),
  );
  const names = definitions.items.map((d) => d.name).sort();

  expect(names).toEqual(['Damage', 'Damage (core)', 'Reach']);
  await context.close();
});

test('a repository built on one the library cannot copy says what to do, and goes on once it can', async ({
  browser,
}) => {
  const { owner, tag, repository: core } = await copyWorld();
  const bridge = await newRepository(owner.api, `Faerûn ${tag}`);

  // The bridge is built on the core, and is offered to a library that is not yet invited to the core.
  const other = await newLibrary(owner.api, `Other ${tag}`);

  await invite(owner.api, core.id, bridge.id);
  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: bridge.id, repository_id: core.id } },
      body: {},
    }),
  );
  await addItem(owner.api, bridge.id, 'Flaming Longsword');
  await publish(owner.api, bridge.id);
  await invite(owner.api, bridge.id, other.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(wizardAddress(other, bridge));
  await expect(page.getByRole('heading', { name: 'It cannot be copied yet' })).toBeVisible();
  await expect(
    page.getByText(`Ask the owner of ${core.name} to invite your library.`),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Continue' })).toBeHidden();

  // The limits are still said: they are what a copy is, whether or not it can be made now.
  await expect(page.getByText('cannot be undone as a whole')).toBeVisible();

  // Once the library is invited to the core, the same page goes on, and counts both.
  await invite(owner.api, core.id, other.id);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Continue' })).toBeVisible();
  await expect(page.locator('[data-brings] > li')).toHaveCount(2);
  await expect(page.locator('[data-brings]')).toContainText(core.name);
  await expect(page.locator('[data-brings]')).toContainText(bridge.name);
  await context.close();
});

test('copying again: replace it, and what that would also remove is said first', async ({
  browser,
}) => {
  const { owner, library, repository } = await copyWorld();

  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: library.id, repository_id: repository.id } },
      body: {},
    }),
  );

  // The library adds a stat of its own to the group it copied.
  const groups = await ok(
    owner.api.GET('/tenants/{tenant_id}/stat-groups', {
      params: { path: { tenant_id: library.id } },
    }),
  );

  await ok(
    owner.api.POST('/tenants/{tenant_id}/stat-definitions', {
      params: { path: { tenant_id: library.id } },
      body: { name: 'Parry', stat_group_id: groups.items[0].id, value_type: 'int' },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  // The repository's page offers it under "More", not as the main thing to do.
  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}`);
  await page.getByText('More', { exact: true }).click();
  await page.getByRole('link', { name: /Copy again/ }).click();
  await expect(page).toHaveURL(/copy=again/);
  await expect(page.getByRole('heading', { name: `Copy ${repository.name} again` })).toBeVisible();

  await page.getByRole('radio', { name: /Replace it/ }).check();
  await expect(page.locator('[data-again-purge]')).toContainText(
    'The earlier copy is removed: 2 entries, 1 stat group, 2 stats. It also removes 1 stat you added to a copied group.',
  );
  await page.getByRole('button', { name: 'Check first' }).click();

  await expect(page.locator('[data-receipt]')).toHaveText(
    'Would add 2 entries, 1 stat group and 2 stats. Nothing has changed yet.',
  );
  await expect(page.locator('[data-previous]')).toContainText('The earlier copy is removed');
  await page.getByRole('button', { name: 'Copy now' }).click();
  await expect(page.locator('[data-done-receipt]')).toContainText('Added 2 entries');

  // Replaced, not doubled; the stat the library had added went with it.
  expect(await holdings(owner.api, library.id)).toEqual({ items: 2, statGroups: 1 });
  await context.close();
});

test('copying again beside the first: the names clash, and are chosen about', async ({
  browser,
}) => {
  const { owner, library, repository } = await copyWorld();

  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: library.id, repository_id: repository.id } },
      body: {},
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(wizardAddress(library, repository, 'again'));
  await expect(page.getByRole('radio', { name: /Keep it as your own/ })).toBeChecked();
  await page.getByRole('button', { name: 'Check first' }).click();

  // The earlier copy's names are in the library now, so they clash.
  await expect(step(page)).toHaveText('Step 2 of 4: Name clashes');
  await expect(page.locator('fieldset.clash')).not.toHaveCount(0);
  await page.getByRole('button', { name: 'Do what is recommended for all' }).click();
  await page.getByRole('button', { name: 'Review the copy' }).click();
  await expect(page.locator('[data-previous]')).toContainText('The earlier copy stays as your own');
  await page.getByRole('button', { name: 'Copy now' }).click();
  await expect(page.locator('[data-done-receipt]')).toContainText('Added 2 entries');

  // The earlier copy's two items stay, and two more came.
  expect((await holdings(owner.api, library.id)).items).toBe(4);
  await context.close();
});

test('a repository that was copied is shown, not copied, when the address asks for a first copy', async ({
  browser,
}) => {
  const { owner, library, repository } = await copyWorld();

  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: library.id, repository_id: repository.id } },
      body: {},
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(wizardAddress(library, repository, 'new'));
  await expect(page.getByRole('heading', { name: repository.name })).toBeVisible();
  await expect(
    page.getByText('Your library has copied this repository, and nothing newer'),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Copy now' })).toHaveCount(0);
  await context.close();
});

test('on a phone, every step is one column and everything pressed is big enough', async ({
  browser,
}) => {
  const { owner, library, repository } = await copyWorld({ clashing: true });
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  async function checkScreen() {
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );

    expect(overflow).toBeLessThanOrEqual(0);

    const heights = await page.evaluate(() =>
      [
        ...document.querySelectorAll<HTMLElement>(
          '[data-copy-view] button, [data-copy-view] .btn, [data-copy-view] .shelf-link, [data-copy-view] .field-row, [data-copy-view] .text-input, [data-copy-view] summary',
        ),
      ]
        .filter((element) => element.offsetParent !== null)
        .map((element) => Math.round(element.getBoundingClientRect().height)),
    );

    expect(heights.length).toBeGreaterThan(0);
    expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  }

  await page.goto(wizardAddress(library, repository));
  await expect(step(page)).toHaveText('Step 1 of 4: Check first');
  await checkScreen();

  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(step(page)).toHaveText('Step 2 of 4: Name clashes');
  await checkScreen();

  await page.getByRole('button', { name: 'Do what is recommended for all' }).click();
  await checkScreen();

  await page.getByRole('button', { name: 'Review the copy' }).click();
  await expect(step(page)).toHaveText('Step 3 of 4: Review');
  await checkScreen();
  await context.close();
});

// The wizard is for someone who may copy: it is not offered to a person with no library of their own,
// and a repository that is not on offer to the library is not one it can open.
test('a repository the library has no invitation to is not copied from an address', async ({
  browser,
}) => {
  const { owner, repository } = await copyWorld();
  const stranger = await newLibrary(owner.api, `Stranger ${crypto.randomUUID()}`);
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(wizardAddress(stranger, repository));
  await expect(page.getByRole('heading', { name: 'Repositories' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Copy now' })).toHaveCount(0);
  await expect(page.locator('[data-copy-view]')).toBeHidden();
  await context.close();
});
