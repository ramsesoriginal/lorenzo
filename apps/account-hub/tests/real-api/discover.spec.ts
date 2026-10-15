import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import { addItem, newLibrary, newRepository, newUser, publish, signedInPage } from './support';

// ADR 0292: Discover and a repository's storefront. The launcher sets PUBLIC_REPOSITORIES_ENABLED for
// this suite (playwright.real-api.config.ts). Every test works in words of its own (a tag in each
// name), since the listing is the whole deployment's and the tests share it.

// A one-pixel PNG, for a cover.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

const list = (page: Page) => page.locator('[data-list-view]');
const results = (page: Page) => page.locator('[data-results] > li');
const storefront = (page: Page) => page.locator('[data-storefront]');

async function makePublic(
  api: Api,
  repositoryId: string,
  body: { summary: string; label?: string; notes?: string },
) {
  await ok(
    api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repositoryId } },
      body: { preview: 'showcase', breaking: false, acknowledge_breaking: true, ...body },
    }),
  );
}

async function copyInto(api: Api, tenantId: string, repositoryId: string) {
  await ok(
    api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: tenantId, repository_id: repositoryId } },
      body: {},
    }),
  );
}

// A public repository with everything a storefront shows, in words made of `tag`.
async function publicWorld() {
  const owner = await newUser('discover-owner', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await addItem(owner.api, repository.id, 'Owlbear');
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}', {
      params: { path: { tenant_id: repository.id } },
      body: { description: 'Every beast there is.\n\nWith its **habits**.' },
    }),
  );
  await makePublic(owner.api, repository.id, {
    summary: `Beasts for the table ${tag}`,
    label: '1.0',
    notes: 'The first release.\nWith two lines.',
  });
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: {
        tags: ['monsters', `tag-${tag}`],
        system: `System ${tag}`,
        languages: ['en', 'de'],
        licence: { label: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
        credits: [{ name: 'Ada Writer', role: 'Writer', url: 'https://ada.example/' }],
      },
    }),
  );
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/profile/cover', {
      params: { path: { tenant_id: repository.id } },
      body: { file: 'cover.png' },
      bodySerializer: () => {
        const data = new FormData();

        data.append('file', new Blob([PNG], { type: 'image/png' }), 'cover.png');

        return data;
      },
    }),
  );

  return { owner, repository, tag };
}

test('a public repository is found by a word and by a tag, and its storefront opens', async ({
  browser,
}) => {
  test.slow();
  const { owner, repository, tag } = await publicWorld();

  // A private one with the same word, which must not be found.
  const hidden = await newRepository(owner.api, `Hidden ${tag}`);

  await addItem(owner.api, hidden.id, 'Secret');
  await publish(owner.api, hidden.id);

  const visitor = await newUser('discover-visitor');
  const { page, context } = await signedInPage(browser, visitor.subject);

  // Discover is in the nav, and the page shows the list.
  await expect(
    page.getByRole('navigation', { name: 'Subpages' }).getByRole('link', { name: 'Discover' }),
  ).toBeVisible();
  await page
    .getByRole('navigation', { name: 'Subpages' })
    .getByRole('link', { name: 'Discover' })
    .click();
  await expect(page).toHaveURL(/\/discover\/$/);
  await expect(page.getByRole('heading', { name: 'Discover', level: 1 })).toBeVisible();
  await expect(list(page)).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Sort by' })).toHaveValue('name');

  // A word: submitted, and kept in the address.
  await page.getByRole('searchbox', { name: 'Search' }).fill(tag);
  await expect(page).toHaveURL(/\/discover\/$/);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`\\?q=${tag}$`));
  await expect(results(page)).toHaveCount(1);
  await expect(page.locator('[data-count]')).toHaveText('1 repository');

  const card = results(page).first();

  await expect(card.getByRole('link', { name: `Bestiary ${tag}` })).toBeVisible();
  await expect(card).toContainText(`Beasts for the table ${tag}`);
  await expect(card.getByText('monsters', { exact: true })).toBeVisible();
  await expect(card).toContainText(`System ${tag} · Release 1.0 · 1 entry`);
  // The cover comes with the token, as a picture, not as a letter.
  await expect(card.locator('[data-picture]')).toBeVisible();
  await expect(card.locator('[data-initial]')).toBeHidden();
  // The private one with the same word is not there, and nothing says how often anything was copied.
  await expect(page.getByText(`Hidden ${tag}`)).toHaveCount(0);
  expect(await list(page).innerText()).not.toMatch(/popular|copied|trending/i);

  // The same list, opened from its address, with the search box filled in.
  await page.goto(`/discover/?q=${tag}`);
  await expect(page.getByRole('searchbox', { name: 'Search' })).toHaveValue(tag);
  await expect(results(page)).toHaveCount(1);

  // A word that matches the summary and not the name finds it too, in any case.
  await page.goto(`/discover/?q=${`BEASTS FOR THE TABLE ${tag}`.toUpperCase()}`);
  await expect(results(page)).toHaveCount(1);

  // A tag, from the choice of tags with how many repositories have it.
  await page.goto('/discover/');
  await page.getByRole('combobox', { name: 'Tag', exact: true }).selectOption(`tag-${tag}`);
  await expect(page).toHaveURL(new RegExp(`\\?tag=tag-${tag}$`));
  await expect(results(page)).toHaveCount(1);
  await expect(page.getByRole('combobox', { name: 'Tag', exact: true })).toHaveValue(`tag-${tag}`);
  await expect(
    page.getByRole('combobox', { name: 'Tag', exact: true }).locator('option:checked'),
  ).toHaveText(`tag-${tag} (1)`);

  // The game system and the language, and the order.
  await page.goto('/discover/');
  await page.getByRole('combobox', { name: 'Game system' }).selectOption(`system ${tag}`);
  await expect(results(page)).toHaveCount(1);
  await page.getByRole('combobox', { name: 'Language' }).selectOption('de');
  await expect(page).toHaveURL(/language=de/);
  await expect(
    page.getByRole('combobox', { name: 'Language' }).locator('option:checked'),
  ).toContainText('German (de)');
  await page.getByRole('combobox', { name: 'Sort by' }).selectOption('released');
  await expect(page).toHaveURL(/sort=released/);
  await expect(results(page)).toHaveCount(1);

  // Nothing found says so, and how to go on.
  await page.goto(`/discover/?q=${tag}-no-such-word`);
  await expect(page.locator('[data-empty]')).toHaveText(
    'Nothing found. Try another word, or remove a filter.',
  );
  await page.getByRole('link', { name: 'Clear the search' }).click();
  await expect(page).toHaveURL(/\/discover\/$/);

  // Open the repository.
  await page.goto(`/discover/?q=${tag}`);
  await card.getByRole('link', { name: `Bestiary ${tag}` }).click();
  await expect(page).toHaveURL(`/discover/?repository=${repository.id}`);
  await expect(list(page)).toBeHidden();
  await expect(storefront(page)).toBeVisible();
  await expect(
    storefront(page).getByRole('heading', { name: `Bestiary ${tag}`, level: 2 }),
  ).toBeVisible();
  await expect(storefront(page).locator('[data-summary]')).toHaveText(
    `Beasts for the table ${tag}`,
  );
  await expect(storefront(page).locator('[data-cover]')).toBeVisible();
  await expect(storefront(page).locator('[data-description]')).toContainText(
    'Every beast there is.',
  );
  await expect(storefront(page).locator('[data-description] strong')).toHaveText('habits');
  await expect(storefront(page).locator('[data-tags]')).toContainText('monsters');
  await expect(storefront(page).locator('[data-facts]')).toContainText(`System ${tag}`);
  await expect(storefront(page).locator('[data-facts]')).toContainText('English (en), German (de)');
  await expect(storefront(page).locator('[data-facts]')).toContainText('Entries');

  // The licence is a link that is not followed or given the page, and the credit is one too.
  const licence = storefront(page).getByRole('link', { name: 'CC BY 4.0' });

  await expect(licence).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/');
  await expect(licence).toHaveAttribute('rel', 'nofollow noopener');

  const credit = storefront(page).getByRole('link', { name: 'Ada Writer' });

  await expect(credit).toHaveAttribute('href', 'https://ada.example/');
  await expect(credit).toHaveAttribute('rel', 'nofollow noopener');
  await expect(storefront(page).locator('[data-credits]')).toContainText('Writer');

  // The latest release with its notes, and no earlier one yet.
  await expect(storefront(page).locator('[data-release]')).toContainText('Release 1.0, ');
  await expect(storefront(page).locator('[data-release-notes]')).toHaveText(
    'The first release.\nWith two lines.',
  );
  await expect(storefront(page).locator('[data-others-section]')).toBeHidden();
  await expect(storefront(page).locator('[data-built-on-none]')).toBeVisible();

  // A second release: the first is an earlier one.
  await addItem(owner.api, repository.id, 'Beholder');
  await publish(owner.api, repository.id);
  await page.reload();
  await expect(storefront(page).locator('[data-others-section]')).toBeVisible();
  await expect(storefront(page).locator('[data-others-title]')).toHaveText('Earlier releases');
  await storefront(page).locator('[data-others-section] summary').click();
  await expect(storefront(page).locator('[data-others]')).toContainText('Release 1.0, ');
  await expect(storefront(page).locator('[data-others]')).toContainText('The first release.');

  // The wording rule, and what is not on the page yet.
  const words = await storefront(page).innerText();

  expect(words).not.toMatch(/tenant|grant|subscri|stable|frozen|popular/i);
  expect(words).not.toMatch(/Report|Publisher|Terms/);

  // Back to the list.
  await storefront(page).getByRole('link', { name: 'All public repositories' }).click();
  await expect(page).toHaveURL(/\/discover\/$/);
  await expect(list(page)).toBeVisible();
  await context.close();
});

test('a private repository, a draft and a repository that is not there are not found', async ({
  browser,
}) => {
  const owner = await newUser('discover-private', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const hidden = await newRepository(owner.api, `Hidden ${tag}`);
  const draft = await newRepository(owner.api, `Draft ${tag}`);

  await addItem(owner.api, hidden.id, 'Secret');
  await publish(owner.api, hidden.id);
  await addItem(owner.api, draft.id, 'Sketch');

  const { page, context } = await signedInPage(browser, owner.subject);

  // The owner does not find their own private repository on Discover either.
  await page.goto(`/discover/?q=${tag}`);
  await expect(page.locator('[data-empty]')).toHaveText(
    'Nothing found. Try another word, or remove a filter.',
  );
  await expect(results(page)).toHaveCount(0);

  for (const id of [hidden.id, draft.id, crypto.randomUUID(), 'not-an-id']) {
    await page.goto(`/discover/?repository=${id}`);
    await expect(page.locator('[data-not-listed]')).toHaveText(
      'This repository is not listed. It may be private, it may not have a release yet, or it may not exist.',
    );
    await expect(storefront(page)).toBeHidden();
  }

  await context.close();
});

test('it is copied into a library that was never invited, and is then in its Shelf', async ({
  browser,
}) => {
  const { repository, tag } = await publicWorld();
  const copier = await newUser('discover-copier', ['tenant_creator']);
  const library = await newLibrary(copier.api, `Table ${tag}`);
  const { page, context } = await signedInPage(browser, copier.subject);

  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(storefront(page).getByRole('heading', { name: `Bestiary ${tag}` })).toBeVisible();

  // Pick the library, then go on to the wizard, which checks first.
  const open = storefront(page).getByRole('button', { name: 'Copy to a library…' });

  await expect(open).toHaveAttribute('aria-expanded', 'false');
  await open.click();
  await expect(open).toHaveAttribute('aria-expanded', 'true');
  await expect(storefront(page).getByLabel('Copy into')).toHaveText(`Table ${tag}`);
  await expect(storefront(page).getByRole('link', { name: 'Continue' })).toHaveAttribute(
    'href',
    `/repositories/?tenant=${library.slug}&repository=${repository.id}&copy=new`,
  );
  await storefront(page).getByRole('link', { name: 'Continue' }).click();

  const wizard = page.locator('[data-copy-view]');

  await expect(wizard.getByRole('heading', { name: `Copy Bestiary ${tag}` })).toBeVisible();
  await expect(wizard.locator('[data-copy-step]')).toHaveText('Step 1 of 3: Check first');
  await expect(wizard.locator('[data-brings]')).toContainText(`Bestiary ${tag}: 1 entry`);
  await expect(wizard.locator('[data-clash-count]')).toHaveText(
    'It clashes with no name in your library.',
  );
  // Back goes to the repository's page on Discover, not to Shelf.
  await expect(wizard.getByRole('link', { name: 'Back to the repository' })).toHaveAttribute(
    'href',
    `/discover/?repository=${repository.id}`,
  );

  await wizard.getByRole('button', { name: 'Continue' }).click();
  await expect(wizard.locator('[data-copy-step]')).toHaveText('Step 2 of 3: Review');
  await expect(wizard.locator('[data-receipt]')).toContainText('Would add 1 entry');
  await expect(wizard.locator('[data-receipt]')).toContainText('Nothing has changed yet.');
  await wizard.getByRole('button', { name: 'Copy now' }).click();
  await expect(wizard.locator('[data-copy-step]')).toHaveText('Step 3 of 3: Done');
  await expect(wizard.locator('[data-done-receipt]')).toContainText('Added 1 entry');

  // It is in the library's Shelf, copied, with its own access.
  await wizard.getByRole('link', { name: 'Open the repository' }).click();
  await expect(page.locator('[data-detail-view] h2[data-name]')).toHaveText(`Bestiary ${tag}`);
  await expect(page.locator('[data-detail-view] header [data-state]')).toHaveText('Copied');

  const subscriptions = await ok(
    copier.api.GET('/tenants/{tenant_id}/repositories', {
      params: { path: { tenant_id: library.id } },
    }),
  );
  const held = subscriptions.items.find((entry) => entry.repository.id === repository.id);

  expect(held?.copied_at).not.toBeNull();

  // Asked for again, the wizard is not opened for what the library holds: its Shelf page is.
  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}&copy=new`);
  await expect(page.locator('[data-detail-view] header [data-state]')).toHaveText('Copied');
  await context.close();
});

test('a copy is for an Owner or an Organizer of a library, and the person is told when there is none', async ({
  browser,
}) => {
  const { repository } = await publicWorld();
  const nobody = await newUser('discover-nobody');
  const { page, context } = await signedInPage(browser, nobody.subject);

  await page.goto(`/discover/?repository=${repository.id}`);
  await storefront(page).getByRole('button', { name: 'Copy to a library…' }).click();
  await expect(page.locator('[data-copy-none]')).toContainText(
    'Repositories are copied into a library, and you are not an Owner or an Organizer of one.',
  );
  await expect(
    page.locator('[data-copy-none]').getByRole('link', { name: 'Your libraries' }),
  ).toHaveAttribute('href', '/tenants/');
  await expect(page.locator('[data-copy-choose]')).toBeHidden();
  await context.close();
});

test('a repository is built on public ones, each a link to its own page', async ({ browser }) => {
  const { owner, repository: core, tag } = await publicWorld();
  const built = await newRepository(owner.api, `Expansion ${tag}`);

  await addItem(owner.api, built.id, 'Dragon');
  await copyInto(owner.api, built.id, core.id);
  await makePublic(owner.api, built.id, { summary: `Built on the bestiary ${tag}` });

  const visitor = await newUser('discover-visitor');
  const { page, context } = await signedInPage(browser, visitor.subject);

  await page.goto(`/discover/?repository=${built.id}`);
  await expect(storefront(page).locator('[data-built-on]')).toContainText(`Bestiary ${tag}`);
  await expect(storefront(page).locator('[data-built-on-none]')).toBeHidden();
  await expect(storefront(page).locator('[data-built-on-note]')).toBeHidden();
  await storefront(page)
    .locator('[data-built-on]')
    .getByRole('link', { name: `Bestiary ${tag}` })
    .click();
  await expect(page).toHaveURL(`/discover/?repository=${core.id}`);
  await expect(storefront(page).getByRole('heading', { name: `Bestiary ${tag}` })).toBeVisible();

  // A repository it is built on that is not public is said so, and not a link; the copy says who to ask.
  await page.route(`**/repositories/${built.id}/dependencies`, async (route) => {
    await route.fulfill({
      json: [{ id: core.id, name: `Bestiary ${tag}`, slug: 'bestiary', public: false }],
    });
  });
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(`/discover/?repository=${built.id}`);
  await expect(storefront(page).locator('[data-built-on]')).toContainText('Not public');
  await expect(storefront(page).locator('[data-built-on]').getByRole('link')).toHaveCount(0);
  await expect(storefront(page).locator('[data-built-on-note]')).toContainText(
    'Ask its Owner to make it public.',
  );
  await context.close();
});

test('a stack with a repository that is not public says so, and who to ask', async ({
  browser,
}) => {
  const { repository, tag } = await publicWorld();
  const copier = await newUser('discover-copier', ['tenant_creator']);
  const library = await newLibrary(copier.api, `Table ${tag}`);
  const { page, context } = await signedInPage(browser, copier.subject);

  // The plan names a repository below it that is neither public nor offered to the library.
  await page.route('**/copy-plan', async (route) => {
    const real = await (await route.fetch()).json();

    await route.fulfill({
      json: {
        ...real,
        steps: [
          {
            repository_id: crypto.randomUUID(),
            name: 'Hidden core',
            granted: false,
            published: true,
            public: false,
            already_copied: false,
            entities: 0,
            stat_groups: 0,
            stat_definitions: 0,
            information: 0,
            attachments: 0,
            dropped: [],
          },
          ...real.steps,
        ],
      },
    });
  });
  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}&copy=new`);

  const wizard = page.locator('[data-copy-view]');

  await expect(wizard.locator('[data-blocked]')).toBeVisible();
  await expect(wizard.locator('[data-missing]')).toHaveText(
    'Hidden core is not public, and your library is not invited to it. Ask its Owner to make it public, or to invite your library.',
  );
  await expect(wizard.getByRole('button', { name: 'Continue' })).toBeHidden();
  await context.close();
});

test('a copy of a repository that is no longer public says so', async ({ browser }) => {
  const { owner, repository, tag } = await publicWorld();
  const copier = await newUser('discover-copier', ['tenant_creator']);
  const library = await newLibrary(copier.api, `Table ${tag}`);
  const { page, context } = await signedInPage(browser, copier.subject);

  await ok(
    owner.api.DELETE('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repository.id }, query: { acknowledge_revokes: true } },
    }),
  );
  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}&copy=new`);
  // Not listed any more, so there is nothing to copy: Shelf shows its list, not the wizard.
  await expect(page.locator('[data-copy-view]')).toBeHidden();
  await expect(page.locator('[data-list-view]')).toBeVisible();
  await context.close();
});

test('there is no link to Discover where the deployment has no public repositories, and the page says so', async ({
  browser,
}) => {
  const visitor = await newUser('discover-visitor');
  const { page, context } = await signedInPage(browser, visitor.subject);

  await page.route('**/discover/facets', async (route) => {
    const real = await (await route.fetch()).json();

    await route.fulfill({
      json: { ...real, enabled: false, tags: [], systems: [], languages: [] },
    });
  });
  // What the header held from the sign-in is not asked again for a while. A request of that
  // sign-in still on its way would write it back after the clear, so it is let finish first.
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => sessionStorage.clear());
  await page.goto('/profile/');
  await expect(
    page.getByRole('navigation', { name: 'Subpages' }).getByRole('link', { name: 'Libraries' }),
  ).toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Subpages' }).getByRole('link', { name: 'Discover' }),
  ).toHaveCount(0);

  // By its address, the page says nothing is public yet, and shows no search.
  await page.goto('/discover/');
  await expect(page.locator('[data-nothing-text]')).toHaveText('Nothing is public yet.');
  await expect(page.getByRole('searchbox')).toHaveCount(0);
  await page.goto('/discover/?repository=abc');
  await expect(page.locator('[data-nothing-text]')).toHaveText('Nothing is public yet.');
  await context.close();
});

test('a list is paged, and a listing too deep is told to narrow it', async ({ browser }) => {
  const visitor = await newUser('discover-visitor');
  const { page, context } = await signedInPage(browser, visitor.subject);

  // The deployment's own listing is short: the pages are shown as the API says there are five.
  await page.route('**/discover/repositories?*', async (route) => {
    const real = await (await route.fetch()).json();

    await route.fulfill({ json: { ...real, total: 100, pages: 5 } });
  });
  await page.goto('/discover/?q=&sort=released&page=2');
  await expect(page.locator('[data-page-of]')).toHaveText('Page 2 of 5');
  await expect(page.getByRole('link', { name: 'Previous' })).toHaveAttribute(
    'href',
    '/discover/?sort=released',
  );
  await expect(page.getByRole('link', { name: 'Next' })).toHaveAttribute(
    'href',
    '/discover/?sort=released&page=3',
  );
  await page.getByRole('link', { name: 'Next' }).click();
  await expect(page).toHaveURL(/page=3/);
  await expect(page.locator('[data-page-of]')).toHaveText('Page 3 of 5');
  await page.unroute('**/discover/repositories?*');

  // Past what the API goes into: the real answer is a refusal, said in words.
  await page.goto('/discover/?page=51');
  await expect(page.locator('[data-too-deep-text]')).toHaveText(
    'Narrow your search with a word or a filter.',
  );
  await page.getByRole('link', { name: 'Go to the first page' }).click();
  await expect(page).toHaveURL(/\/discover\/$/);
  await expect(page.locator('[data-too-deep]')).toBeHidden();

  // A page after the last has nothing, and leads back.
  await page.goto('/discover/?page=40');
  await expect(page.locator('[data-empty]')).toBeVisible();
  await context.close();
});

test('on a phone, the list and the storefront fit and everything pressed is big enough', async ({
  browser,
}) => {
  const { repository, tag } = await publicWorld();
  const copier = await newUser('discover-copier', ['tenant_creator']);

  await newLibrary(copier.api, `Table ${tag}`);

  const { page, context } = await signedInPage(browser, copier.subject, {
    viewport: { width: 375, height: 812 },
  });

  async function fits() {
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );

    expect(overflow).toBeLessThanOrEqual(0);

    const pressed = await page.evaluate(() =>
      [
        ...document.querySelectorAll<HTMLElement>(
          '[data-discover] button, [data-discover] a.btn, [data-discover] .shelf-link, [data-discover] select, [data-discover] input',
        ),
      ]
        .filter((element) => element.offsetParent !== null)
        .map((element) => ({
          what: element.textContent?.trim() || element.getAttribute('name') || element.tagName,
          height: Math.round(element.getBoundingClientRect().height),
        })),
    );

    expect(pressed.length).toBeGreaterThanOrEqual(3);
    for (const target of pressed) expect(target.height, target.what).toBeGreaterThanOrEqual(44);
  }

  await page.goto(`/discover/?q=${tag}`);
  await expect(results(page)).toHaveCount(1);
  await fits();

  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(storefront(page).getByRole('heading', { name: `Bestiary ${tag}` })).toBeVisible();
  await expect(storefront(page).locator('[data-cover]')).toBeVisible();
  await storefront(page).getByRole('button', { name: 'Copy to a library…' }).click();
  await expect(storefront(page).getByRole('link', { name: 'Continue' })).toBeVisible();
  await fits();

  // The cover is the width of the page, not wider.
  const cover = await storefront(page).locator('[data-cover]').boundingBox();

  expect((cover?.x ?? -1) >= 0 && (cover?.x ?? 0) + (cover?.width ?? 0) <= 375).toBe(true);
  await context.close();
});
