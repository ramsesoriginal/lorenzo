import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import { addItem, newLibrary, newRepository, newUser, signedInPage } from './support';

// ADR 0432, RFC 0051 H2: a public repository its Owner left off Discover. The launcher sets
// PUBLIC_REPOSITORIES_ENABLED for this suite (playwright.real-api.config.ts). Every test works in
// words of its own (a tag in each name), since the listing is the whole deployment's.

const WORDS_NEVER_ON_SCREEN = /tenant|grant|subscri|flatten|\bsource/i;

const results = (page: Page) => page.locator('[data-results] > li');
const card = (page: Page) => page.locator('[data-visibility]');
const listedBox = (page: Page) => card(page).getByRole('checkbox', { name: 'Listed on Discover' });
const tagChoice = (page: Page) => page.getByRole('combobox', { name: 'Tag', exact: true });

async function makePublic(api: Api, repositoryId: string, summary: string) {
  await ok(
    api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repositoryId } },
      body: {
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
        accept_terms: true,
        summary,
      },
    }),
  );
}

// A public repository with a tag and a system of its own.
async function publicWorld(prefix: string) {
  const owner = await newUser(`${prefix}-owner`, ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await addItem(owner.api, repository.id, 'Owlbear');
  await makePublic(owner.api, repository.id, `Beasts for the table ${tag}`);
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: { tags: [`tag-${tag}`], system: `System ${tag}`, languages: ['en'] },
    }),
  );

  return { owner, repository, tag };
}

test('an Owner leaves a public repository off Discover and a library still opens and copies it by its address', async ({
  browser,
}) => {
  test.slow();
  const { owner, repository, tag } = await publicWorld('unlisted');
  const visitor = await newUser('unlisted-visitor', ['tenant_creator']);
  const library = await newLibrary(visitor.api, `Table ${tag}`);
  const guest = await signedInPage(browser, visitor.subject);
  const studio = await signedInPage(browser, owner.subject);

  // Listed to begin with: found by its word and by its tag.
  await guest.page.goto(`/discover/?q=${tag}`);
  await expect(results(guest.page)).toHaveCount(1);
  await guest.page.goto('/discover/');
  await expect(tagChoice(guest.page).locator('option', { hasText: `tag-${tag} (1)` })).toHaveCount(
    1,
  );

  // Studio's visibility card has the switch, on, with what it means.
  await studio.page.goto(`/studio/?repository=${repository.slug}`);
  await expect(card(studio.page).locator('[data-visibility-state]')).toHaveText('Public');
  await expect(listedBox(studio.page)).toBeChecked();
  await expect(card(studio.page).locator('[data-visibility-listed-help]')).toContainText(
    'Anyone signed in to Lorenzo can find it on Discover.',
  );

  // Turned off: saved at once, and the card says what stays.
  await listedBox(studio.page).uncheck();
  await expect(card(studio.page).locator('[data-visibility-status]')).toHaveText('Saved.');
  await expect(listedBox(studio.page)).not.toBeChecked();
  await expect(card(studio.page).locator('[data-visibility-listed-help]')).toContainText(
    'It is not on Discover, and no search finds it.',
  );
  await expect(card(studio.page).locator('[data-visibility-listed-help]')).toContainText(
    'Anyone who has its address can still open its page and copy it',
  );
  expect(await card(studio.page).innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);
  // The address to share is the page's own link.
  await expect(card(studio.page).getByRole('link', { name: 'Open its page' })).toHaveAttribute(
    'href',
    `/discover/?repository=${repository.id}`,
  );
  expect(
    (
      await ok(
        owner.api.GET('/tenants/{tenant_id}/profile', {
          params: { path: { tenant_id: repository.id } },
        }),
      )
    ).listed,
  ).toBe(false);
  // It is kept: a reload says the same.
  await studio.page.reload();
  await expect(listedBox(studio.page)).not.toBeChecked();

  // Off Discover: not found by its word, not offered as a tag, not counted in a facet.
  await guest.page.goto(`/discover/?q=${tag}`);
  await expect(guest.page.locator('[data-empty]')).toHaveText(
    'Nothing found. Try another word, or remove a filter.',
  );
  await expect(results(guest.page)).toHaveCount(0);
  await guest.page.goto('/discover/');
  await expect(tagChoice(guest.page).locator('option', { hasText: `tag-${tag}` })).toHaveCount(0);
  const facets = await ok(visitor.api.GET('/discover/facets'));

  expect(facets.tags.map((facet) => facet.value)).not.toContain(`tag-${tag}`);
  expect(facets.systems.map((facet) => facet.value)).not.toContain(`system ${tag}`);

  // Opened by its address, its page is the same page as ever, and it says nothing to a visitor.
  await guest.page.goto(`/discover/?repository=${repository.id}`);
  await expect(guest.page.locator('[data-storefront]')).toBeVisible();
  await expect(
    guest.page.locator('[data-storefront]').getByRole('heading', {
      name: `Bestiary ${tag}`,
      level: 2,
    }),
  ).toBeVisible();
  await expect(guest.page.locator('[data-storefront] [data-summary]')).toHaveText(
    `Beasts for the table ${tag}`,
  );
  await expect(guest.page.locator('[data-not-listed]')).toBeHidden();
  await expect(guest.page.locator('[data-unlisted-note]')).toBeHidden();

  // Its Owners are told it is not listed, in words.
  await studio.page.goto(`/discover/?repository=${repository.id}`);
  await expect(studio.page.locator('[data-unlisted-note]')).toHaveText(
    'This repository is not listed on Discover. Only people who have its address can open this page.',
  );
  expect(await studio.page.locator('[data-unlisted-note]').innerText()).not.toMatch(
    WORDS_NEVER_ON_SCREEN,
  );

  // A library copies it by its address.
  await ok(
    visitor.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: library.id, repository_id: repository.id } },
      body: {},
    }),
  );

  const items = await ok(
    visitor.api.GET('/tenants/{tenant_id}/items', {
      params: { path: { tenant_id: library.id } },
    }),
  );

  expect(items.items.map((item) => item.title)).toEqual(['Owlbear']);

  // Turned on again: found again, and the note is gone.
  await studio.page.goto(`/studio/?repository=${repository.slug}`);
  await listedBox(studio.page).check();
  await expect(card(studio.page).locator('[data-visibility-status]')).toHaveText('Saved.');
  await expect(card(studio.page).locator('[data-visibility-listed-help]')).toContainText(
    'Anyone signed in to Lorenzo can find it on Discover.',
  );
  await guest.page.goto(`/discover/?q=${tag}`);
  await expect(results(guest.page)).toHaveCount(1);
  await studio.page.goto(`/discover/?repository=${repository.id}`);
  await expect(studio.page.locator('[data-storefront]')).toBeVisible();
  await expect(studio.page.locator('[data-unlisted-note]')).toBeHidden();

  await studio.context.close();
  await guest.context.close();
});

test('a private repository has no such switch, and an Author is not offered it', async ({
  browser,
}) => {
  test.slow();
  const { owner, repository } = await publicWorld('unlisted-gate');
  const author = await newUser('unlisted-author');

  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: repository.id } },
      body: { user_id: author.me.id, role: 'author' },
    }),
  );

  // Not public: the API refuses to leave it off a listing it is not on, in words.
  const draft = await newRepository(owner.api, `Draft ${crypto.randomUUID().slice(0, 8)}`);
  const refused = await owner.api.PATCH('/tenants/{tenant_id}/profile', {
    params: { path: { tenant_id: draft.id } },
    body: { listed: false },
  });

  expect(refused.response.status).toBe(409);
  expect(JSON.stringify(refused.error)).toContain('repository-not-public');
  expect(JSON.stringify(refused.error)).not.toMatch(WORDS_NEVER_ON_SCREEN);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${draft.slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
  await expect(page.locator('[data-visibility-listed]')).toBeHidden();

  // An Author reads the repository and has no card at all.
  const reader = await signedInPage(browser, author.subject);

  await reader.page.goto(`/studio/?repository=${repository.slug}`);
  await expect(reader.page.locator('[data-overview] [data-state]')).toBeVisible();
  await expect(card(reader.page)).toBeHidden();
  const forbidden = await author.api.PATCH('/tenants/{tenant_id}/profile', {
    params: { path: { tenant_id: repository.id } },
    body: { listed: false },
  });

  expect(forbidden.response.status).toBe(403);

  await reader.context.close();
  await context.close();
});

test('on a phone, the switch is one column, big enough to press, and the note does not push the page sideways', async ({
  browser,
}) => {
  test.slow();
  const { owner, repository } = await publicWorld('unlisted-phone');

  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: { listed: false },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });
  const noScroll = () =>
    page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );

  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(listedBox(page)).toBeVisible();
  expect(
    (
      await card(page)
        .locator('label.field-row')
        .filter({ hasText: 'Listed on Discover' })
        .boundingBox()
    )?.height ?? 0,
  ).toBeGreaterThanOrEqual(44);
  expect(await noScroll()).toBeLessThanOrEqual(0);

  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(page.locator('[data-unlisted-note]')).toBeVisible();
  expect(await noScroll()).toBeLessThanOrEqual(0);

  const box = await page.locator('[data-unlisted-note]').boundingBox();

  expect(box).not.toBeNull();
  expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= 375).toBe(true);
  await context.close();
});
