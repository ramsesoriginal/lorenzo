import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addItem,
  invite,
  newLibrary,
  newRepository,
  newUser,
  publish,
  signedInPage,
} from './support';

// ADR 0297: Studio when the platform's operators have taken a repository off Discover. Its members
// read a notice on the Overview, in words, with the reason; the visibility card cannot make it
// public; and everything else works as ever, since they have to be able to fix it. Operators have
// no screen: they delist through the API, as these specs do.

type Person = Awaited<ReturnType<typeof newUser>>;

const notice = (page: Page) => page.locator('[data-delisted]');
const card = (page: Page) => page.locator('[data-visibility]');

async function overview(page: Page, slug: string) {
  await page.goto(`/studio/?repository=${slug}`);
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

async function delist(operator: Person, repositoryId: string, reason: string) {
  await ok(
    operator.api.PUT('/admin/repositories/{repository_id}/delist', {
      params: { path: { repository_id: repositoryId } },
      body: { reason },
    }),
  );
}

async function relist(operator: Person, repositoryId: string) {
  await ok(
    operator.api.DELETE('/admin/repositories/{repository_id}/delist', {
      params: { path: { repository_id: repositoryId } },
    }),
  );
}

// A released repository with an Owner, an Organizer and an Author, a library invited to it, and an
// operator.
async function world() {
  const owner = await newUser('owner', ['tenant_creator']);
  const organizer = await newUser('organizer');
  const author = await newUser('author');
  const operator = await newUser('operator', ['platform-operator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await addItem(owner.api, repository.id, 'Owlbear');
  await addMember(owner, repository.id, organizer, 'orga');
  await addMember(owner, repository.id, author, 'author');
  await publish(owner.api, repository.id);

  const library = await newLibrary(owner.api, `Table ${tag}`);

  await invite(owner.api, repository.id, library.id);

  return { owner, organizer, author, operator, repository, library, tag };
}

const REASON = 'It copies the work of another publisher';

test('every member reads that the repository was taken off Discover, why, and what it means', async ({
  browser,
}) => {
  const { owner, organizer, author, operator, repository } = await world();

  for (const person of [owner, organizer, author]) {
    const { page, context } = await signedInPage(browser, person.subject);

    // Listed: no notice.
    await overview(page, repository.slug);
    await expect(notice(page)).toBeHidden();
    await context.close();
  }

  await delist(operator, repository.id, REASON);

  for (const person of [owner, organizer, author]) {
    const { page, context } = await signedInPage(browser, person.subject);

    await overview(page, repository.slug);
    await expect(notice(page)).toBeVisible();
    await expect(notice(page)).toContainText(
      "This repository was taken off Discover by the platform's operators.",
    );
    await expect(notice(page)).toContainText(`Reason: ${REASON}`);
    await expect(notice(page)).toContainText(
      'Libraries that copied it keep their copies, and cannot update from it until it is listed again.',
    );
    // In words people use: no architecture, and nobody's name.
    expect(await notice(page).innerText()).not.toMatch(/tenant|grant|subscri|delist/i);
    await context.close();
  }

  // Listed again: it goes.
  await relist(operator, repository.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(notice(page)).toBeHidden();
  await context.close();
});

test('its members fix it: the Overview, the releases and the editing work as ever', async ({
  browser,
}) => {
  const { owner, operator, repository } = await world();

  await delist(operator, repository.id, REASON);

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(notice(page)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Publish a new release…' })).toBeEnabled();
  await expect(page.getByRole('button', { name: /^Edit / })).toBeVisible();

  // A release is still made through its dialog, and the notice stays.
  await page.getByRole('button', { name: 'Publish a new release…' }).click();
  await expect(page.locator('[data-publish-dialog]')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(notice(page)).toBeVisible();
  await context.close();
});

test('the card cannot make a delisted repository public, and says why', async ({ browser }) => {
  const { owner, operator, repository } = await world();

  await delist(operator, repository.id, REASON);

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(card(page)).toBeVisible();
  await expect(page.locator('[data-visibility-state]')).toHaveText('Private');

  const button = card(page).getByRole('button', { name: 'Make public…' });

  await expect(button).toBeDisabled();
  await expect(page.locator('[data-visibility-note]')).toHaveText(
    "It cannot be made public while it is off Discover. The platform's operators can list it again.",
  );

  // Listed again, it can: the card reads the repository fresh when the page opens.
  await relist(operator, repository.id);
  await overview(page, repository.slug);
  await expect(card(page).getByRole('button', { name: 'Make public…' })).toBeEnabled();
  await expect(page.locator('[data-visibility-note]')).toBeHidden();
  await context.close();
});

test('on a phone, the notice fits and says all of it', async ({ browser }) => {
  const { author, operator, repository } = await world();

  await delist(operator, repository.id, REASON);

  const { page, context } = await signedInPage(browser, author.subject, {
    viewport: { width: 375, height: 812 },
  });

  await overview(page, repository.slug);
  await expect(notice(page)).toBeVisible();

  const box = await notice(page).boundingBox();

  expect(box).not.toBeNull();
  expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= 375).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await context.close();
});
