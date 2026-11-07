import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addItem,
  invite,
  newLibrary,
  newRepository,
  newUser,
  publish,
  signedInPage,
} from './support';

// ADR 0384: an Owner retires a repository. Studio: the Owner's card (a message, a dialog that says how
// many libraries hold it, "Bring it back"), the notice every member reads, and the visibility card
// that cannot make a retired repository public. Shelf: a library that holds it reads "Retired" and
// the Owner's words, keeps its updates, and is offered no copy. Discover and the storefront no longer
// have it. Nothing here reads a repository's text, so a GM-only note is never on these pages: what is
// shown is the Owner's message, which the Owner wrote to be read.

type Person = Awaited<ReturnType<typeof newUser>>;

const MESSAGE = 'Use Bestiary 2 instead';

const notice = (page: Page) => page.locator('[data-retired]').first();
const card = (page: Page) => page.locator('[data-retire]');

async function overview(page: Page, slug: string) {
  await page.goto(`/repositories/?repository=${slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
}

async function addMember(owner: Person, tenantId: string, person: Person, role: string) {
  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: tenantId } },
      body: { user_id: person.me.id, role: role as 'owner' | 'orga' | 'author' },
    }),
  );
}

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
        label: '1.0',
      },
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

async function retire(owner: Person, repositoryId: string, message?: string) {
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/deprecation', {
      params: { path: { tenant_id: repositoryId } },
      body: message ? { message } : {},
    }),
  );
}

async function bringBack(owner: Person, repositoryId: string) {
  await ok(
    owner.api.DELETE('/tenants/{tenant_id}/deprecation', {
      params: { path: { tenant_id: repositoryId } },
    }),
  );
}

// A public repository with an Owner, an Organizer and an Author; a library invited to it that has not
// copied it (`invitee`), a library that copied it by itself, as from Discover (`holder`), and a
// visitor with no library.
async function world() {
  const owner = await newUser('owner', ['tenant_creator']);
  const organizer = await newUser('organizer');
  const author = await newUser('author');
  const holder = await newUser('holder', ['tenant_creator']);
  const visitor = await newUser('visitor');
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await addItem(owner.api, repository.id, 'Owlbear');
  await addMember(owner, repository.id, organizer, 'orga');
  await addMember(owner, repository.id, author, 'author');
  await makePublic(owner.api, repository.id, `Beasts for the table ${tag}`);

  const invitee = await newLibrary(owner.api, `Invitee ${tag}`);

  await invite(owner.api, repository.id, invitee.id);

  const holderLibrary = await newLibrary(holder.api, `Holder ${tag}`);

  await copyInto(holder.api, holderLibrary.id, repository.id);

  return { owner, organizer, author, holder, visitor, repository, invitee, holderLibrary, tag };
}

test('the Owner retires a repository with a message, and brings it back', async ({ browser }) => {
  test.slow();
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(notice(page)).toBeHidden();
  await expect(card(page)).toBeVisible();
  await expect(card(page).getByRole('heading', { name: 'Retire this repository' })).toBeVisible();
  await expect(card(page)).toContainText(
    'Libraries that already copied it keep their copy and its updates. Nobody can copy it any more, and it leaves Discover.',
  );

  // The message has a counter, and a limit.
  const field = card(page).getByRole('textbox', { name: 'Message for the libraries (optional)' });

  await expect(card(page).locator('[data-retire-count]')).toHaveText('0 of 500 characters');
  await field.fill(MESSAGE);
  await expect(card(page).locator('[data-retire-count]')).toHaveText(
    `${MESSAGE.length} of 500 characters`,
  );

  // The dialog says how many libraries hold it, and that they will be told.
  await card(page).getByRole('button', { name: 'Retire…' }).click();

  const dialog = page.locator('[data-retire-dialog]');

  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('heading', { name: `Retire ${repository.name}?` })).toBeVisible();
  await expect(dialog).toContainText(
    '2 libraries hold it. They keep their copy and its updates, and they will be told that you retired it.',
  );
  await expect(dialog).toContainText('Nobody can copy it any more, and it leaves Discover.');
  await expect(dialog).toContainText(`Message: ${MESSAGE}`);

  // Cancelling retires nothing.
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(dialog).toBeHidden();
  await expect(notice(page)).toBeHidden();

  await card(page).getByRole('button', { name: 'Retire…' }).click();
  await dialog.getByRole('button', { name: 'Retire it' }).click();
  await expect(dialog).toBeHidden();

  // The card now shows the message and the way back; the notice says it to everyone.
  await expect(card(page).locator('[data-retire-retired]')).toBeVisible();
  await expect(card(page).locator('[data-retire-retired]')).toContainText(
    'This repository is retired.',
  );
  await expect(card(page).locator('[data-retire-retired]')).toContainText(`Message: ${MESSAGE}`);
  await expect(card(page).getByRole('button', { name: 'Bring it back' })).toBeVisible();
  await expect(notice(page)).toBeVisible();
  await expect(notice(page)).toContainText('This repository is retired.');
  await expect(notice(page)).toContainText(
    'Libraries that copied it keep their copy and its updates. It cannot be copied or found in Discover.',
  );
  await expect(notice(page)).toContainText(`Message: ${MESSAGE}`);
  expect(await notice(page).innerText()).not.toMatch(/tenant|grant|subscri|deprecat/i);

  // Bring it back: the card offers to retire it again, the notice goes.
  await card(page).getByRole('button', { name: 'Bring it back' }).click();
  await expect(card(page).locator('[data-retire-form-box]')).toBeVisible();
  await expect(notice(page)).toBeHidden();
  await context.close();
});

test('every other member reads the notice, with the message, and has no card', async ({
  browser,
}) => {
  const { owner, organizer, author, repository } = await world();

  await retire(owner, repository.id, MESSAGE);

  for (const person of [organizer, author]) {
    const { page, context } = await signedInPage(browser, person.subject);

    await overview(page, repository.slug);
    await expect(notice(page)).toBeVisible();
    await expect(notice(page)).toContainText('This repository is retired.');
    await expect(notice(page)).toContainText(`Message: ${MESSAGE}`);
    await expect(card(page)).toBeHidden();
    // Whoever works on it can go on working: nothing is closed to them.
    await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
    await context.close();
  }
});

test('Discover and the storefront no longer have it, and have it again when it is back', async ({
  browser,
}) => {
  const { owner, visitor, repository, tag } = await world();
  const { page, context } = await signedInPage(browser, visitor.subject);

  // Held in the page before: the visitor looked at it while it was listed.
  await page.goto(`/discover/?q=${tag}`);
  await expect(page.locator('[data-results] > li')).toHaveCount(1);
  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(page.locator('[data-storefront]')).toBeVisible();

  await retire(owner, repository.id, MESSAGE);

  // Not a held answer: the list and the page ask again, and it is gone.
  await page.goto(`/discover/?q=${tag}`);
  await expect(page.locator('[data-results] > li')).toHaveCount(0);
  await expect(page.locator('[data-empty]')).toBeVisible();
  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(page.locator('[data-storefront]')).toBeHidden();
  await expect(page.locator('[data-not-listed]')).toBeVisible();

  await bringBack(owner, repository.id);
  await page.goto(`/discover/?q=${tag}`);
  await expect(page.locator('[data-results] > li')).toHaveCount(1);
  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(page.locator('[data-storefront]')).toBeVisible();
  await context.close();
});

test('a library that holds it reads it is retired, keeps its updates, and is offered no copy', async ({
  browser,
}) => {
  test.slow();
  const { owner, holder, repository, invitee, holderLibrary } = await world();

  await retire(owner, repository.id, MESSAGE);
  // The Owner goes on releasing: the library that copied it takes the release.
  await addItem(owner.api, repository.id, 'Beholder');
  await publish(owner.api, repository.id);

  // The library that copied it.
  const held = await signedInPage(browser, holder.subject);

  await held.page.goto(`/repositories/?tenant=${holderLibrary.slug}`);

  const row = held.page
    .locator('[data-list-view]')
    .getByRole('listitem')
    .filter({ hasText: repository.name });

  await expect(row).toContainText('Retired');
  await expect(row).toContainText(`Message from its Owner: ${MESSAGE}`);
  await expect(row).toContainText('Update announced');
  await row.getByRole('link', { name: repository.name }).click();

  const detail = held.page.locator('[data-detail-view]');

  await expect(detail.locator('[data-retired]')).toBeVisible();
  await expect(detail.locator('[data-retired]')).toContainText('Retired');
  await expect(detail.locator('[data-retired]')).toContainText(
    'Its Owner retired this repository. Your library keeps its copy and its updates, and it cannot be copied again.',
  );
  await expect(detail.locator('[data-retired]')).toContainText(
    `Message from its Owner: ${MESSAGE}`,
  );
  // Its update is there to take, and nothing offers another copy.
  await expect(detail.locator('[data-updates-actions]')).toBeVisible();
  await expect(detail.getByRole('link', { name: 'Check for updates' })).toBeVisible();
  await expect(detail.locator('[data-actions]')).toBeHidden();
  await expect(detail.locator('[data-more]')).toBeHidden();
  await expect(detail.getByRole('link', { name: 'Copy this repository' })).toBeHidden();

  // A link to copy it again does not open the wizard.
  await held.page.goto(
    `/repositories/?tenant=${holderLibrary.slug}&repository=${repository.id}&copy=again`,
  );
  await expect(held.page.locator('[data-copy-view]')).toBeHidden();
  await expect(detail.locator('[data-retired]')).toBeVisible();
  await held.context.close();

  // The library that holds only an invitation reads that it can no longer be copied.
  const invited = await signedInPage(browser, owner.subject);

  await invited.page.goto(`/repositories/?tenant=${invitee.slug}`);
  await invited.page
    .locator('[data-list-view]')
    .getByRole('listitem')
    .filter({ hasText: repository.name })
    .getByRole('link', { name: repository.name })
    .click();

  const only = invited.page.locator('[data-detail-view]');

  await expect(only.locator('[data-retired]')).toContainText(
    'This repository is retired and can no longer be copied.',
  );
  await expect(only.locator('[data-actions]')).toBeHidden();
  await expect(only.getByRole('link', { name: 'Copy this repository' })).toBeHidden();
  await invited.page.goto(
    `/repositories/?tenant=${invitee.slug}&repository=${repository.id}&copy=new`,
  );
  await expect(invited.page.locator('[data-copy-view]')).toBeHidden();
  await expect(only.locator('[data-retired]')).toBeVisible();

  // Brought back, the copy is offered again and nothing says it is retired.
  await bringBack(owner, repository.id);
  await invited.page.goto(`/repositories/?tenant=${invitee.slug}&repository=${repository.id}`);
  // What the page held for a few seconds is asked again by a reload, as the hub does everywhere.
  await invited.page.reload();
  await expect(only.locator('[data-retired]')).toBeHidden();
  await expect(only.getByRole('link', { name: 'Copy this repository' })).toBeVisible();
  await invited.context.close();
});

test('the visibility card cannot make a retired repository public, and says why', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Private ${crypto.randomUUID().slice(0, 8)}`);

  await addItem(owner.api, repository.id, 'Owlbear');
  await publish(owner.api, repository.id);
  await retire(owner, repository.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(page.locator('[data-visibility]')).toBeVisible();

  const button = page.locator('[data-visibility]').getByRole('button', { name: 'Make public…' });

  await expect(button).toBeDisabled();
  await expect(page.locator('[data-visibility-note]')).toHaveText(
    'It cannot be made public while it is retired. Bring it back first.',
  );
  // With no message, the notice says only what it means.
  await expect(notice(page)).toBeVisible();
  await expect(notice(page).locator('[data-retired-message]')).toBeHidden();

  await bringBack(owner, repository.id);
  await overview(page, repository.slug);
  await expect(
    page.locator('[data-visibility]').getByRole('button', { name: 'Make public…' }),
  ).toBeEnabled();
  await context.close();
});

test('on a phone, the card, the dialog and the notice fit and can be pressed', async ({
  browser,
}) => {
  const { owner, author, repository } = await world();
  const phone = { viewport: { width: 375, height: 812 } };
  const { page, context } = await signedInPage(browser, owner.subject, phone);

  await overview(page, repository.slug);
  await card(page).getByRole('textbox').fill(MESSAGE);

  const retireButton = card(page).getByRole('button', { name: 'Retire…' });

  expect((await retireButton.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  await retireButton.click();

  const dialog = page.locator('[data-retire-dialog]');

  await expect(dialog).toBeVisible();

  const box = await dialog.boundingBox();

  expect(box).not.toBeNull();
  expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= 375).toBe(true);
  for (const name of ['Cancel', 'Retire it']) {
    expect(
      (await dialog.getByRole('button', { name }).boundingBox())?.height ?? 0,
    ).toBeGreaterThanOrEqual(44);
  }
  await dialog.getByRole('button', { name: 'Retire it' }).click();
  await expect(notice(page)).toBeVisible();

  const bring = card(page).getByRole('button', { name: 'Bring it back' });

  expect((await bring.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);

  const notified = await notice(page).boundingBox();

  expect(notified).not.toBeNull();
  expect((notified?.x ?? -1) >= 0 && (notified?.x ?? 0) + (notified?.width ?? 0) <= 375).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await context.close();

  // A member who only reads sees the notice at the same width.
  const reader = await signedInPage(browser, author.subject, phone);

  await overview(reader.page, repository.slug);
  await expect(notice(reader.page)).toBeVisible();
  expect(
    await reader.page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await reader.context.close();
});
