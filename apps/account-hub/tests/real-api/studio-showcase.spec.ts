import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import { feature, goPublic, previewWorld, SECRET_TEXT, watchAnswers } from './preview-support';
import { addItem, newUser, signedInPage } from './support';

// ADR 0293: Studio's "What people can look at": the Owner's choice of how much can be looked at before
// copying, and the entries they feature. The launcher sets PUBLIC_REPOSITORIES_ENABLED for this suite
// (playwright.real-api.config.ts). The card is shown for a repository whether it is public or not.

const card = (page: Page) => page.locator('[data-showcase]');
const featured = (page: Page) => card(page).locator('[data-featured-list] > li');
const names = (page: Page) => featured(page).locator('[data-name]');

async function overview(page: Page, slug: string) {
  await page.goto(`/studio/?repository=${slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
}

async function profileOf(api: Api, repositoryId: string) {
  return ok(
    api.GET('/tenants/{tenant_id}/profile', { params: { path: { tenant_id: repositoryId } } }),
  );
}

async function showcaseOf(api: Api, repositoryId: string) {
  return ok(
    api.GET('/tenants/{tenant_id}/showcase', { params: { path: { tenant_id: repositoryId } } }),
  );
}

async function add(page: Page, word: string, name: string) {
  await card(page).getByRole('searchbox', { name: 'Add an entry' }).fill(word);
  await card(page)
    .getByRole('button', { name: `Add: ${name}` })
    .click();
  await expect(card(page).locator('[data-featured-status]')).toHaveText('Saved.');
}

test('an Owner chooses what people can look at, and the card keeps it', async ({ browser }) => {
  test.slow();
  const world = await previewWorld('showcase-choice');
  const { page } = await signedInPage(browser, world.owner.subject);

  // A private repository has the card too: its holders look inside as well.
  await overview(page, world.repository.slug);
  await expect(card(page)).toBeVisible();
  await expect(card(page).getByRole('heading', { name: 'What people can look at' })).toBeVisible();
  await expect(card(page).getByText('What can people look at before they copy it?')).toBeVisible();

  // The default, and the words of the dialog that makes a repository public.
  const showcase = card(page).getByRole('radio', {
    name: 'People can look at the entries you feature before copying.',
  });
  const everyEntry = card(page).getByRole('radio', { name: 'People can look at every entry.' });
  const off = card(page).getByRole('radio', { name: 'People see its summary and counts only.' });

  await expect(showcase).toBeChecked();
  expect((await profileOf(world.owner.api, world.repository.id)).preview).toBe('showcase');

  await everyEntry.check();
  await expect(card(page).locator('[data-showcase-choice-status]')).toHaveText('Saved.');
  expect((await profileOf(world.owner.api, world.repository.id)).preview).toBe('public');

  await off.check();
  await expect(card(page).locator('[data-showcase-choice-status]')).toHaveText('Saved.');
  expect((await profileOf(world.owner.api, world.repository.id)).preview).toBe('off');

  await page.reload();
  await expect(
    card(page).getByRole('radio', { name: 'People see its summary and counts only.' }),
  ).toBeChecked();
});

test('an Owner features entries, orders them, removes one, and the API holds the list', async ({
  browser,
}) => {
  test.slow();
  const world = await previewWorld('showcase-list');
  const { page } = await signedInPage(browser, world.owner.subject);

  await overview(page, world.repository.slug);
  await expect(card(page).locator('[data-featured-none]')).toHaveText(
    'No entries are featured yet.',
  );
  await expect(card(page).locator('[data-featured-count]')).toContainText(
    '0 of 12 entries featured',
  );
  await expect(card(page).locator('[data-featured-count]')).toContainText(
    'You can feature up to 12 entries.',
  );
  await expect(card(page)).toContainText(
    'Visitors read the latest release, so an entry you add is shown from the next release.',
  );

  // Added by searching the repository's entries; what is featured is not offered again.
  await add(page, 'owl', 'Owlbear');
  await add(page, 'grif', 'Griffin');
  await expect(names(page)).toHaveText(['Owlbear', 'Griffin']);
  await card(page).getByRole('searchbox', { name: 'Add an entry' }).fill('owl');
  await expect(card(page).locator('[data-featured-add-none]')).toHaveText(
    'No entry with that name is left to add.',
  );
  await card(page).getByRole('searchbox', { name: 'Add an entry' }).fill('');

  const held = async () =>
    (await showcaseOf(world.owner.api, world.repository.id)).entries.map((e) => e.name);

  expect(await held()).toEqual(['Owlbear', 'Griffin']);

  // The first cannot go up and the last cannot go down.
  await expect(card(page).getByRole('button', { name: 'Move up: Owlbear' })).toBeDisabled();
  await expect(card(page).getByRole('button', { name: 'Move down: Griffin' })).toBeDisabled();

  await card(page).getByRole('button', { name: 'Move down: Owlbear' }).click();
  await expect(names(page)).toHaveText(['Griffin', 'Owlbear']);
  expect(await held()).toEqual(['Griffin', 'Owlbear']);

  await add(page, 'bas', 'Basilisk');
  await card(page).getByRole('button', { name: 'Remove: Griffin' }).click();
  await expect(names(page)).toHaveText(['Owlbear', 'Basilisk']);
  expect(await held()).toEqual(['Owlbear', 'Basilisk']);

  // Kept: the page reads it again.
  await page.reload();
  await expect(names(page)).toHaveText(['Owlbear', 'Basilisk']);
});

test('twelve are the most an Owner can feature, and the card says so', async ({ browser }) => {
  test.slow();
  const world = await previewWorld('showcase-limit');
  const extra: string[] = [];

  for (let i = 1; i <= 10; i++) {
    extra.push((await addItem(world.owner.api, world.repository.id, `Creature ${i}`)).entity_id);
  }

  await feature(world.owner.api, world.repository.id, [world.owlbear, world.griffin, ...extra]);

  const { page } = await signedInPage(browser, world.owner.subject);

  await overview(page, world.repository.slug);
  await expect(featured(page)).toHaveCount(12);
  await expect(card(page).locator('[data-featured-count]')).toContainText(
    '12 of 12 entries featured',
  );
  // No room for a thirteenth: the search is closed.
  await expect(card(page).getByRole('searchbox', { name: 'Add an entry' })).toBeDisabled();

  await card(page).getByRole('button', { name: 'Remove: Creature 10' }).click();
  await expect(featured(page)).toHaveCount(11);
  await expect(card(page).getByRole('searchbox', { name: 'Add an entry' })).toBeEnabled();
});

test('what the Owner features in Studio is what a visitor sees', async ({ browser }) => {
  test.slow();
  const world = await previewWorld('showcase-visitor');
  const owner = await signedInPage(browser, world.owner.subject);

  await overview(owner.page, world.repository.slug);
  await add(owner.page, 'grif', 'Griffin');
  await add(owner.page, 'owl', 'Owlbear');

  // Public with what Studio chose, in the release the visitor reads.
  await goPublic(world.owner.api, world.repository.id, `Chosen ${world.tag}`, 'showcase');

  const visitor = await newUser('showcase-visitor');
  const reader = await signedInPage(browser, visitor.subject);
  const answers = watchAnswers(reader.page);

  await reader.page.goto(`/discover/?repository=${world.repository.id}`);

  const cards = reader.page.locator('[data-storefront] [data-preview-featured] > li');

  await expect(cards).toHaveCount(2);
  await expect(cards.locator('h4')).toHaveText(['Griffin', 'Owlbear']);
  await expect(cards.nth(1)).toContainText('Hunts at night,');
  await expect(reader.page.locator('[data-storefront]')).not.toContainText('Basilisk');
  await expect(reader.page.locator('[data-storefront]')).not.toContainText(SECRET_TEXT);
  expect(answers.bodies.join('\n')).not.toContain(SECRET_TEXT);
  expect(answers.urls.join('\n')).not.toContain(world.secretPictureId);
});

test('the card is the Owner`s: an Organizer does not see it', async ({ browser }) => {
  const world = await previewWorld('showcase-orga');
  const orga = await newUser('showcase-orga');

  await ok(
    world.owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: world.repository.id } },
      body: { user_id: orga.me.id, role: 'orga' },
    }),
  );

  const { page } = await signedInPage(browser, orga.subject);

  await overview(page, world.repository.slug);
  await expect(page.locator('[data-showcase]')).toBeHidden();
});

test('at 375 pixels the card fits and everything pressed is easy to press', async ({ browser }) => {
  test.slow();
  const world = await previewWorld('showcase-phone');

  await feature(world.owner.api, world.repository.id, [world.owlbear, world.griffin]);

  const { page } = await signedInPage(browser, world.owner.subject, {
    viewport: { width: 375, height: 800 },
  });

  await overview(page, world.repository.slug);
  await expect(card(page)).toBeVisible();
  await card(page).scrollIntoViewIfNeeded();

  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );

  expect(wide).toBe(false);

  for (const name of ['Move down: Owlbear', 'Remove: Owlbear', 'Remove: Griffin']) {
    const box = await card(page).getByRole('button', { name }).boundingBox();

    expect(box?.height ?? 0, name).toBeGreaterThanOrEqual(44);
  }

  const radio = await card(page)
    .getByRole('radio', { name: 'People can look at every entry.' })
    .locator('xpath=ancestor::label')
    .boundingBox();

  expect(radio?.height ?? 0).toBeGreaterThanOrEqual(44);
});
