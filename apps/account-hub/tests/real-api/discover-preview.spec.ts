import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  feature,
  goPublic,
  previewWorld,
  SECRET_TEXT,
  SECRET_TITLE,
  setLevel,
  watchAnswers,
} from './preview-support';
import { invite, newLibrary, newUser, publish, signedInPage } from './support';

// ADR 0293: what a reader may look at of a repository before copying it, on its page in Discover (a
// visitor) and in Shelf (a library that holds it). The launcher sets PUBLIC_REPOSITORIES_ENABLED for
// this suite (playwright.real-api.config.ts). Every test works in words of its own (a tag in each
// name), since the listing is the whole deployment's and the tests share it.

const preview = (page: Page) => page.locator('[data-storefront] [data-preview]');
const cards = (page: Page) => preview(page).locator('[data-preview-featured] > li');
const dialog = (page: Page) => preview(page).locator('[data-preview-dialog]');

async function openStorefront(page: Page, repositoryId: string) {
  await page.goto(`/discover/?repository=${repositoryId}`);
  await expect(page.locator('[data-storefront]')).toBeVisible();
}

// GM only text and its picture come out of nothing a reader is given.
async function expectNoSecret(
  page: Page,
  answers: ReturnType<typeof watchAnswers>,
  secretPictureId: string,
) {
  const text = await page.locator('body').innerText();

  expect(text).not.toContain(SECRET_TEXT);
  expect(text).not.toContain(SECRET_TITLE);
  expect(await page.content()).not.toContain(SECRET_TEXT);
  expect(answers.bodies.join('\n')).not.toContain(SECRET_TEXT);
  expect(answers.bodies.join('\n')).not.toContain(SECRET_TITLE);
  expect(answers.urls.join('\n')).not.toContain(secretPictureId);
}

async function noOverflow(page: Page) {
  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );

  expect(wide).toBe(false);
}

test('at showcase a visitor sees exactly the featured entries, with their text and picture', async ({
  browser,
}) => {
  test.slow();
  const world = await previewWorld('preview-showcase');

  // The Owner features two of the three, in an order of their own.
  await feature(world.owner.api, world.repository.id, [world.griffin, world.owlbear]);
  await goPublic(world.owner.api, world.repository.id, `Beasts ${world.tag}`, 'showcase');

  const visitor = await newUser('preview-visitor');
  const { page } = await signedInPage(browser, visitor.subject);
  const answers = watchAnswers(page);

  await openStorefront(page, world.repository.id);
  await expect(preview(page).getByRole('heading', { name: 'Look inside', level: 3 })).toBeVisible();
  await expect(cards(page)).toHaveCount(2);
  await expect(cards(page).nth(0).getByRole('heading', { level: 4 })).toHaveText('Griffin');
  await expect(cards(page).nth(1).getByRole('heading', { level: 4 })).toHaveText('Owlbear');

  const owlbear = cards(page).nth(1);

  await expect(owlbear).toContainText('Featured');
  await expect(owlbear).toContainText('Item');
  // Its Everyone's text, rendered, with its picture shown from the token-fetched blob.
  await expect(owlbear.getByRole('heading', { name: 'Habits', level: 5 })).toBeVisible();
  await expect(owlbear.getByText('Hunts at night,')).toBeVisible();
  await expect(owlbear.locator('strong', { hasText: 'loudly' })).toBeVisible();
  await expect(owlbear.locator('img.preview-picture')).toBeVisible();
  await expect
    .poll(() =>
      owlbear.locator('img.preview-picture').evaluate((img: HTMLImageElement) => img.naturalWidth),
    )
    .toBeGreaterThan(0);
  // Its stat value.
  await expect(owlbear.getByText('Physical', { exact: true })).toBeVisible();
  await expect(owlbear.getByText('Weight', { exact: true })).toBeVisible();
  await expect(owlbear.locator('dd', { hasText: '4' })).toBeVisible();
  await expect(cards(page).nth(0)).toContainText('Nests on high cliffs.');

  // The one that is not featured is not here, and there is no list to find it in.
  await expect(preview(page)).not.toContainText('Basilisk');
  await expect(preview(page)).not.toContainText('Turns the unwary to stone.');
  await expect(preview(page).locator('[data-preview-all]')).toBeHidden();

  // The API says the same: no look at an entry that is not featured, for a visitor.
  const refused = await visitor.api.GET('/repositories/{repository_id}/entities/{entity_id}', {
    params: { path: { repository_id: world.repository.id, entity_id: world.basilisk } },
  });

  expect(refused.response.status).toBe(404);

  await expectNoSecret(page, answers, world.secretPictureId);
});

test('at showcase with nothing featured it says so', async ({ browser }) => {
  const world = await previewWorld('preview-nothing');

  await goPublic(world.owner.api, world.repository.id, `Nothing ${world.tag}`, 'showcase');

  const visitor = await newUser('preview-visitor');
  const { page } = await signedInPage(browser, visitor.subject);

  await openStorefront(page, world.repository.id);
  await expect(preview(page).locator('[data-preview-line]')).toHaveText(
    'The Owner has not chosen entries to show yet.',
  );
  await expect(cards(page)).toHaveCount(0);
});

test('at off a visitor is told the Owner has not opened it, and sees no entry', async ({
  browser,
}) => {
  const world = await previewWorld('preview-off');

  await feature(world.owner.api, world.repository.id, [world.owlbear]);
  await goPublic(world.owner.api, world.repository.id, `Off ${world.tag}`, 'off');

  const visitor = await newUser('preview-visitor');
  const { page } = await signedInPage(browser, visitor.subject);
  const answers = watchAnswers(page);

  await openStorefront(page, world.repository.id);
  await expect(preview(page).locator('[data-preview-line]')).toHaveText(
    'The Owner has not opened this repository for a look inside.',
  );
  await expect(cards(page)).toHaveCount(0);
  await expect(preview(page).locator('[data-preview-all]')).toBeHidden();
  await expect(page.locator('[data-storefront]')).not.toContainText('Owlbear');

  await expectNoSecret(page, answers, world.secretPictureId);
});

test('at public a visitor finds any entry, and opens it in a dialog', async ({ browser }) => {
  test.slow();
  const world = await previewWorld('preview-public');

  await feature(world.owner.api, world.repository.id, [world.owlbear]);
  await goPublic(world.owner.api, world.repository.id, `Every entry ${world.tag}`, 'public');

  const visitor = await newUser('preview-visitor');
  const { page } = await signedInPage(browser, visitor.subject);
  const answers = watchAnswers(page);

  await openStorefront(page, world.repository.id);

  // The featured one first, as a card; then every entry, found by a word.
  await expect(cards(page)).toHaveCount(1);
  await expect(cards(page).first()).toContainText('Owlbear');

  const all = preview(page).locator('[data-preview-all]');

  await expect(all).toBeVisible();
  await expect(all.getByRole('heading', { name: 'All entries' })).toBeVisible();
  await expect(all.locator('[data-preview-list] > li')).toHaveCount(3);
  await expect(all.locator('[data-preview-count]')).toHaveText('3 entries');

  await all.getByRole('searchbox', { name: 'Find an entry' }).fill('basil');
  await expect(all.locator('[data-preview-list] > li')).toHaveCount(1);
  await expect(all.locator('[data-preview-list] > li').first()).toContainText('Basilisk');

  // One that is not featured opens, with its text.
  await all.getByRole('button', { name: 'Look at Basilisk' }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page)).toContainText('Basilisk');
  await expect(dialog(page)).toContainText('Gaze');
  await expect(dialog(page)).toContainText('Turns the unwary to stone.');
  await expect(dialog(page)).not.toContainText('Featured');
  await dialog(page).getByRole('button', { name: 'Close' }).click();
  await expect(dialog(page)).toBeHidden();

  // A search with no match says so.
  await all.getByRole('searchbox', { name: 'Find an entry' }).fill('zzzz');
  await expect(all.locator('[data-preview-empty]')).toHaveText('No entry matches.');

  // The one with GM only text opens with its Everyone's text alone.
  await all.getByRole('searchbox', { name: 'Find an entry' }).fill('owl');
  await all.getByRole('button', { name: 'Look at Owlbear' }).click();
  await expect(dialog(page)).toContainText('Hunts at night,');
  await dialog(page).getByRole('button', { name: 'Close' }).click();

  await expectNoSecret(page, answers, world.secretPictureId);
});

test('a visitor`s preview follows the Owner`s switch when it changes', async ({ browser }) => {
  const world = await previewWorld('preview-switch');

  await feature(world.owner.api, world.repository.id, [world.owlbear]);
  await goPublic(world.owner.api, world.repository.id, `Switch ${world.tag}`, 'showcase');

  const visitor = await newUser('preview-visitor');
  const { page } = await signedInPage(browser, visitor.subject);

  await openStorefront(page, world.repository.id);
  await expect(cards(page)).toHaveCount(1);

  await setLevel(world.owner.api, world.repository.id, 'off');
  await page.reload();
  await expect(preview(page).locator('[data-preview-line]')).toHaveText(
    'The Owner has not opened this repository for a look inside.',
  );
  await expect(cards(page)).toHaveCount(0);
});

test('at 375 pixels the preview and its dialog fit and are easy to press', async ({ browser }) => {
  test.slow();
  const world = await previewWorld('preview-phone');

  await feature(world.owner.api, world.repository.id, [world.owlbear, world.griffin]);
  await goPublic(world.owner.api, world.repository.id, `Phone ${world.tag}`, 'public');

  const visitor = await newUser('preview-visitor');
  const { page } = await signedInPage(browser, visitor.subject, {
    viewport: { width: 375, height: 800 },
  });

  await openStorefront(page, world.repository.id);
  await expect(cards(page)).toHaveCount(2);
  await expect(
    cards(page).first().locator('img.preview-picture, [data-texts]').first(),
  ).toBeVisible();
  await noOverflow(page);

  const look = preview(page).getByRole('button', { name: 'Look at Griffin' });

  await look.scrollIntoViewIfNeeded();

  const box = await look.boundingBox();

  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);

  await look.click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page)).toContainText('Nests on high cliffs.');
  await noOverflow(page);

  const dialogBox = await dialog(page).boundingBox();

  expect(dialogBox?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect((dialogBox?.x ?? 0) + (dialogBox?.width ?? 0)).toBeLessThanOrEqual(375);

  const close = dialog(page).getByRole('button', { name: 'Close' });

  expect((await close.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  await close.click();
  await expect(dialog(page)).toBeHidden();
});

test('a library that holds the repository sees every name and the text the switch says', async ({
  browser,
}) => {
  test.slow();
  const world = await previewWorld('preview-holder');
  const reader = await newUser('preview-holder-reader', ['tenant_creator']);
  const library = await newLibrary(reader.api, `Table ${world.tag}`);

  // Held by invitation, and private: the holder's column is the only one that applies.
  await feature(world.owner.api, world.repository.id, [world.owlbear]);
  await publish(world.owner.api, world.repository.id);
  await invite(world.owner.api, world.repository.id, library.id);

  const { page } = await signedInPage(browser, reader.subject);
  const answers = watchAnswers(page);
  const shelf = `/repositories/?tenant=${library.slug}&repository=${world.repository.id}`;
  const look = page.locator('[data-detail-view] [data-preview]');

  // At showcase: the featured entry with its text, on the repository's page.
  await page.goto(shelf);
  await expect(page.locator('[data-detail-view]')).toBeVisible();
  await expect(look.getByRole('heading', { name: 'Look inside', level: 3 })).toBeVisible();
  await expect(look.locator('[data-preview-featured] > li')).toHaveCount(1);
  await expect(look.locator('[data-preview-featured] > li').first()).toContainText('Owlbear');
  await expect(look.locator('[data-preview-featured] > li').first()).toContainText(
    'Hunts at night,',
  );
  await expect(look.locator('img.preview-picture')).toBeVisible();

  // Every name is in the list; one that is not featured opens with its name, kind and no text.
  await page.locator('[data-entries-section] summary').click();
  await expect(page.locator('[data-entries] > li')).toHaveCount(3);
  await page.getByRole('button', { name: 'Look at Basilisk' }).click();
  await expect(look.locator('[data-preview-dialog]')).toBeVisible();
  await expect(look.locator('[data-preview-dialog]')).toContainText('Basilisk');
  await expect(look.locator('[data-preview-dialog]')).toContainText('Item');
  await expect(look.locator('[data-preview-dialog]')).toContainText(
    'The Owner has not opened the text of this entry for a look.',
  );
  await expect(look.locator('[data-preview-dialog]')).not.toContainText('Turns the unwary');
  await look.locator('[data-preview-dialog]').getByRole('button', { name: 'Close' }).click();

  // The featured one opens with its text.
  await page.getByRole('button', { name: 'Look at Owlbear' }).click();
  await expect(look.locator('[data-preview-dialog]')).toContainText('Hunts at night,');
  await look.locator('[data-preview-dialog]').getByRole('button', { name: 'Close' }).click();

  // At public the Owner's switch opens every entry's text to a holder too.
  await setLevel(world.owner.api, world.repository.id, 'public');
  await page.goto(shelf);
  await page.locator('[data-entries-section] summary').click();
  await page.getByRole('button', { name: 'Look at Basilisk' }).click();
  await expect(look.locator('[data-preview-dialog]')).toContainText('Turns the unwary to stone.');
  await look.locator('[data-preview-dialog]').getByRole('button', { name: 'Close' }).click();

  // At off the names stay and there is nothing to look at: no featured card, no button.
  await setLevel(world.owner.api, world.repository.id, 'off');
  await page.goto(shelf);
  await expect(look.locator('[data-preview-line]')).toContainText(
    'The Owner has not opened the text of this repository for a look.',
  );
  await expect(look.locator('[data-preview-featured] > li')).toHaveCount(0);
  await page.locator('[data-entries-section] summary').click();
  await expect(page.locator('[data-entries] > li')).toHaveCount(3);
  await expect(page.getByRole('button', { name: /^Look at / })).toHaveCount(0);

  await expectNoSecret(page, answers, world.secretPictureId);
});

test('the API gives a visitor no picture of a row that is GM only, under any entry', async () => {
  const world = await previewWorld('preview-secret');

  await feature(world.owner.api, world.repository.id, [world.owlbear]);
  await goPublic(world.owner.api, world.repository.id, `Secret ${world.tag}`, 'public');

  const visitor = await newUser('preview-visitor');
  const owlbear = await ok(
    visitor.api.GET('/repositories/{repository_id}/entities/{entity_id}', {
      params: { path: { repository_id: world.repository.id, entity_id: world.owlbear } },
    }),
  );

  expect(owlbear.information.map((row) => row.title)).toEqual(['Habits']);

  for (const entity of [world.owlbear, world.griffin, world.basilisk]) {
    const picture = await visitor.api.GET(
      '/repositories/{repository_id}/entities/{entity_id}/pictures/{payload_id}',
      {
        params: {
          path: {
            repository_id: world.repository.id,
            entity_id: entity,
            payload_id: world.secretPictureId,
          },
        },
        parseAs: 'blob',
      },
    );

    expect(picture.response.status).toBe(404);
  }
});

test('at 375 pixels a holder`s look inside fits and its buttons are easy to press', async ({
  browser,
}) => {
  test.slow();
  const world = await previewWorld('preview-holder-phone');
  const reader = await newUser('preview-holder-phone-reader', ['tenant_creator']);
  const library = await newLibrary(reader.api, `Table ${world.tag}`);

  await feature(world.owner.api, world.repository.id, [world.owlbear]);
  await publish(world.owner.api, world.repository.id);
  await invite(world.owner.api, world.repository.id, library.id);

  const { page } = await signedInPage(browser, reader.subject, {
    viewport: { width: 375, height: 800 },
  });

  await page.goto(`/repositories/?tenant=${library.slug}&repository=${world.repository.id}`);

  const look = page.locator('[data-detail-view] [data-preview]');

  await expect(look.locator('[data-preview-featured] > li')).toHaveCount(1);
  await noOverflow(page);
  await page.locator('[data-entries-section] summary').click();

  const button = page.getByRole('button', { name: 'Look at Basilisk' });

  await button.scrollIntoViewIfNeeded();
  expect((await button.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  await button.click();
  await expect(look.locator('[data-preview-dialog]')).toBeVisible();
  await noOverflow(page);

  const box = await look.locator('[data-preview-dialog]').boundingBox();

  expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(375);
});
