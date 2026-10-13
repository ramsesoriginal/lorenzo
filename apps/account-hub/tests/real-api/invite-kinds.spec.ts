import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  AUTHGEAR_URL,
  SITE_URL,
  SUBJECT_COOKIE,
} from '../../../inventory-web/tests/e2e/support/env';
import { newLibrary, newRepository, newUser } from './support';

// The invite links of a library or repository (ADR 0220), end to end: an Owner's role link and
// library link made through the API, a visitor opening them in the built site, logging in through
// the fake Authgear and accepting, and the join page's box for a pasted code.

type Person = Awaited<ReturnType<typeof newUser>>;

const inAWeek = () => new Date(Date.now() + 6 * 24 * 60 * 60 * 1000).toISOString();

async function roleLink(owner: Person, tenantId: string, role: 'author' | 'orga', maxUses = 1) {
  return ok(
    owner.api.POST('/tenants/{tenant_id}/invites', {
      params: { path: { tenant_id: tenantId } },
      body: { kind: 'tenant_role', role, max_uses: maxUses, expires_at: inAWeek() },
    }),
  );
}

async function libraryLink(owner: Person, repositoryId: string) {
  return ok(
    owner.api.POST('/tenants/{tenant_id}/invites', {
      params: { path: { tenant_id: repositoryId } },
      body: { kind: 'library_access' },
    }),
  );
}

/** A visitor's browser, not yet logged in. */
async function visitor(browser: import('@playwright/test').Browser, subject: string) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await context.addCookies([{ name: SUBJECT_COOKIE, value: subject, url: AUTHGEAR_URL }]);
  return { context, page };
}

/** The log-in round trip on /join, which brings the page back to the same link. */
async function logIn(page: Page) {
  await page.getByRole('button', { name: 'Log in to join' }).click();
  await expect(page).toHaveURL(`${SITE_URL}/join/`);
}

test('an Author link: a visitor logs in, joins as an Author, and the next person is told it is dead', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api, `Table ${crypto.randomUUID()}`);
  const created = await roleLink(owner, library.id, 'author');
  const nia = await newUser('nia');
  const { context, page } = await visitor(browser, nia.subject);

  await page.goto(`/join/#${created.token}`);
  // Before any login: what it is for and what joining makes you, in the three names.
  await expect(page.locator('[data-campaign]')).toHaveText(library.name);
  await expect(page.locator('[data-offer]')).toHaveText(
    `You've been invited to join the library ${library.name} as an Author.`,
  );
  expect(page.url()).toBe(`${SITE_URL}/join/`);
  expect(await page.evaluate(() => sessionStorage.getItem('lorenzo.invite'))).toBe(created.token);

  await logIn(page);
  await page.getByRole('button', { name: 'Join as an Author' }).click();
  await expect(page.locator('[data-status]')).toHaveText(
    `You're in. ${library.name} lists you as an Author.`,
  );
  await expect(page.getByRole('link', { name: 'Open it' })).toHaveAttribute(
    'href',
    /\/tenants\/\?tenant=/,
  );
  expect(await page.evaluate(() => sessionStorage.getItem('lorenzo.invite'))).toBeNull();
  const me = await ok(nia.api.GET('/me'));
  expect(me.memberships.map((m) => [m.tenant_id, m.role])).toEqual([[library.id, 'author']]);

  // A link made for one person is that person's: the next one finds it dead.
  const other = await newUser('other');
  const second = await visitor(browser, other.subject);
  await second.page.goto(`/join/#${created.token}`);
  await expect(second.page.locator('[data-dead]')).toHaveText(
    "This link doesn't work any more. Ask whoever sent it for a new one.",
  );
  await second.context.close();
  await context.close();
});

test('a pasted code on the join page opens the link and joins an Organizer of a repository', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api);
  const created = await roleLink(owner, repository.id, 'orga');
  const lena = await newUser('lena');
  const { context, page } = await visitor(browser, lena.subject);

  await page.goto('/join/');
  await expect(page.locator('[data-paste]')).toBeVisible();
  await page.getByLabel('Invite link or code').fill(created.token);
  await page.getByRole('button', { name: 'Open invite' }).click();
  await expect(page.locator('[data-offer]')).toHaveText(
    `You've been invited to join the repository ${repository.name} as an Organizer.`,
  );
  await logIn(page);
  await page.getByRole('button', { name: 'Join as an Organizer' }).click();
  await expect(page.locator('[data-status]')).toHaveText(
    `You're in. ${repository.name} lists you as an Organizer.`,
  );
  await expect(page.getByRole('link', { name: 'Open it' })).toHaveAttribute(
    'href',
    `/studio/?repository=${repository.id}`,
  );
  const me = await ok(lena.api.GET('/me'));
  expect(me.memberships.map((m) => m.role)).toEqual(['orga']);
  await context.close();
});

test('a library link: the visitor chooses one of the libraries they own, and only those are offered', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Faerun ${crypto.randomUUID()}`);
  const created = await libraryLink(owner, repository.id);

  const gm = await newUser('gm', ['tenant_creator']);
  const mine = await newLibrary(gm.api, `Mine ${crypto.randomUUID()}`);
  const another = await newLibrary(gm.api, `Another ${crypto.randomUUID()}`);
  // A library of someone else's where they are an Organizer only: not theirs to share with.
  const friend = await newUser('friend', ['tenant_creator']);
  const theirs = await newLibrary(friend.api, `Theirs ${crypto.randomUUID()}`);
  await ok(
    friend.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: theirs.id } },
      body: { user_id: gm.me.id, role: 'orga' },
    }),
  );

  const { context, page } = await visitor(browser, gm.subject);
  await page.goto(`/join/#${created.token}`);
  await expect(page.locator('[data-offer]')).toContainText(
    `The repository ${repository.name} is being shared with a library of yours.`,
  );
  await logIn(page);

  const choice = page.getByLabel('Share it with');
  await expect(choice).toBeVisible();
  const options = await choice.locator('option').allTextContents();
  expect(options.sort()).toEqual([`${another.name} (library)`, `${mine.name} (library)`].sort());
  await choice.selectOption({ label: `${mine.name} (library)` });
  await page.getByRole('button', { name: 'Share' }).click();
  await expect(page.locator('[data-status]')).toHaveText(
    `${repository.name} is now shared with ${mine.name}.`,
  );

  const subscribers = await ok(
    owner.api.GET('/tenants/{tenant_id}/subscribers', {
      params: { path: { tenant_id: repository.id } },
    }),
  );
  expect(subscribers.items.map((s) => s.tenant_id)).toEqual([mine.id]);
  await context.close();
});

test('a library link for someone who owns no library says so, and offers to make one only if they may', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api);
  const created = await libraryLink(owner, repository.id);

  const cannot = await newUser('cannot');
  const first = await visitor(browser, cannot.subject);
  await first.page.goto(`/join/#${created.token}`);
  await logIn(first.page);
  await expect(first.page.locator('[data-no-library]')).toContainText(
    "You aren't an Owner of a library yet",
  );
  await expect(first.page.getByRole('link', { name: 'Make a library' })).toBeHidden();
  await expect(first.page.getByRole('button', { name: 'Share' })).toBeHidden();

  const may = await newUser('may', ['tenant_creator']);
  const second = await visitor(browser, may.subject);
  await second.page.goto(`/join/#${created.token}`);
  await logIn(second.page);
  await expect(second.page.getByRole('link', { name: 'Make a library' })).toBeVisible();

  // Nothing was shared, and the link is still good.
  const subscribers = await ok(
    owner.api.GET('/tenants/{tenant_id}/subscribers', {
      params: { path: { tenant_id: repository.id } },
    }),
  );
  expect(subscribers.items).toEqual([]);
  await first.context.close();
  await second.context.close();
});

test('the join page fits a phone', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(
    owner.api,
    `A repository with a rather long name ${crypto.randomUUID()}`,
  );
  const created = await libraryLink(owner, repository.id);
  const gm = await newUser('gm', ['tenant_creator']);
  await newLibrary(gm.api, `A library with a long name too ${crypto.randomUUID()}`);
  const context = await browser.newContext({ viewport: { width: 375, height: 800 } });
  const page = await context.newPage();
  await context.addCookies([{ name: SUBJECT_COOKIE, value: gm.subject, url: AUTHGEAR_URL }]);
  await page.goto(`/join/#${created.token}`);
  await logIn(page);
  await expect(page.getByLabel('Share it with')).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await context.close();
});
