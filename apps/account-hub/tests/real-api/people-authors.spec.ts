import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import { AUTHGEAR_URL, SUBJECT_COOKIE } from '../../../inventory-web/tests/e2e/support/env';
import { newLibrary, newRepository, newUser, openLibrary, signedInPage } from './support';

// People with the Author role, and the links that bring people in (ADR 0212): the Owner's panel in a
// repository and in a library, an Author's own view, and a link followed end to end.

type Person = Awaited<ReturnType<typeof newUser>>;

async function addMember(owner: Person, tenantId: string, person: Person, role: string) {
  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: tenantId } },
      body: { user_id: person.me.id, role: role as 'owner' | 'orga' | 'author' },
    }),
  );
}

async function repositoryWorld() {
  const owner = await newUser('owner', ['tenant_creator']);
  const author = await newUser('author');
  const repository = await newRepository(owner.api, `Bestiary ${crypto.randomUUID().slice(0, 8)}`);

  await addMember(owner, repository.id, author, 'author');

  return { owner, author, repository };
}

async function openPeople(page: Page, slug: string) {
  await page.goto(`/studio/?repository=${slug}`);
  await page.getByRole('tab', { name: 'People' }).click();

  return page.locator('[data-people]');
}

const invitesOf = (owner: Person, tenantId: string) =>
  ok(
    owner.api.GET('/tenants/{tenant_id}/invites', {
      params: { path: { tenant_id: tenantId } },
    }),
  );

test('an Owner sees every role with what it allows, and changes a person between the three', async ({
  browser,
}) => {
  const { owner, author, repository } = await repositoryWorld();
  const { page, context } = await signedInPage(browser, owner.subject);
  const people = await openPeople(page, repository.slug);

  await expect(people.locator('[data-roles] strong')).toHaveText(['Owner', 'Organizer', 'Author']);
  await expect(people).toContainText('Edits what is in it: entries, stats and notes.');
  await expect(people).not.toContainText(/\borga\b/);

  // The choice offers Author, and each row says who added the person.
  const row = people.locator('[data-members] > li').filter({ hasText: author.me.id });

  await expect(row.getByRole('combobox')).toHaveValue('author');
  await expect(row.getByRole('option')).toHaveText(['Owner', 'Organizer', 'Author']);
  await expect(row.locator('[data-added-by]')).toContainText('Added by');

  await row.getByRole('combobox').selectOption('orga');
  await expect
    .poll(async () => {
      const roster = await ok(
        owner.api.GET('/tenants/{tenant_id}/memberships', {
          params: { path: { tenant_id: repository.id } },
        }),
      );

      return roster.items.find((m) => m.kind === 'membership' && m.user_id === author.me.id);
    })
    .toMatchObject({ role: 'orga' });
  await context.close();
});

test('an Owner makes an Author link, sees it once, lists it without its token, and revokes it', async ({
  browser,
}) => {
  const { owner, repository } = await repositoryWorld();
  const { page, context } = await signedInPage(browser, owner.subject, {
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  const people = await openPeople(page, repository.slug);
  const links = people.locator('[data-tenant-invite-links]');

  // Never an Owner: the choice has two roles. An Organizer link is for one person.
  await expect(links.locator('[data-role] option')).toHaveText(['Author', 'Organizer']);
  await links.locator('[data-team]').fill('11');
  await links.getByRole('button', { name: 'Make a link' }).click();
  await expect(links).toContainText('Use a whole number from 1 to 10');
  expect((await invitesOf(owner, repository.id)).items).toEqual([]);

  await links.locator('[data-role]').selectOption('orga');
  await expect(links.locator('[data-team-field]')).toBeHidden();
  await links.locator('[data-role]').selectOption('author');
  await links.locator('[data-team]').fill('3');
  await links.getByRole('button', { name: 'Make a link' }).click();

  const link = links.getByLabel('Author invite link');

  await expect(link).toBeVisible();
  const url = await link.inputValue();

  expect(url).toMatch(/\/join\/#[A-Za-z0-9_-]{43}$/);
  await expect(links).toContainText("won't be shown again");
  await expect(links).toContainText(
    'The first 3 people to open it become Authors of this repository',
  );
  await links.getByRole('button', { name: 'Copy' }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(url);

  const [made] = (await invitesOf(owner, repository.id)).items;

  expect([made?.kind, made?.role, made?.max_uses]).toEqual(['tenant_role', 'author', 3]);

  const token = url.split('#')[1] ?? '';
  const item = links.locator('[data-list] > li').first();

  await expect(item).toContainText('Active');
  await expect(item).toContainText('Author link');
  await expect(item).toContainText('Used 0 of 3');
  await expect(links.locator('[data-list]')).not.toContainText(token);

  await links.getByRole('button', { name: 'Done' }).click();
  await expect(links.getByLabel('Author invite link')).toHaveCount(0);
  await page.reload();
  expect(await page.content()).not.toContain(token);

  await page.getByRole('tab', { name: 'People' }).click();
  await links.getByRole('button', { name: 'Revoke' }).click();
  await expect(links.locator('[data-list] > li').first()).toContainText('Revoked');
  expect((await invitesOf(owner, repository.id)).items[0]?.revoked_at).not.toBeNull();
  await context.close();
});

test('a person follows an Author link, joins, and then reads the repository as an Author', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Lore ${crypto.randomUUID().slice(0, 8)}`);
  const made = await ok(
    owner.api.POST('/tenants/{tenant_id}/invites', {
      params: { path: { tenant_id: repository.id } },
      body: { kind: 'tenant_role', role: 'author' },
    }),
  );
  const nia = await newUser('nia');
  const context = await browser.newContext();
  const page = await context.newPage();

  await context.addCookies([{ name: SUBJECT_COOKIE, value: nia.subject, url: AUTHGEAR_URL }]);
  await page.goto(`/join/#${made.token}`);
  await page.getByRole('button', { name: 'Log in to join' }).click();
  await page.getByRole('button', { name: 'Join as an Author' }).click();
  await expect(page.locator('[data-status]')).toContainText('lists you as an Author');

  // Opened in Studio, the way the page offers.
  await page.getByRole('link', { name: 'Open it' }).click();
  await expect(page.getByRole('heading', { name: repository.name })).toBeVisible();
  await expect(page.locator('[data-role]').first()).toHaveText('Author');
  await context.close();
});

test('an Author sees their own role, what each role allows, and only the tabs the API gives them', async ({
  browser,
}) => {
  const { author, repository } = await repositoryWorld();
  const { page, context } = await signedInPage(browser, author.subject);
  const people = await openPeople(page, repository.slug);

  await expect(people.locator('[data-roles] strong')).toHaveText(['Owner', 'Organizer', 'Author']);
  await expect(people.locator('[data-people-list] > li')).toHaveCount(1);
  await expect(people.locator('[data-people-list] > li')).toContainText('You');
  await expect(people.locator('[data-people-list] [data-person-role]')).toHaveText('Author');

  // No controls for people, no links, no tabs the API refuses: who copies it, and the activity.
  await expect(people.locator('[data-tenant-invite-links]')).toHaveCount(0);
  await expect(people.locator('[data-members]')).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Libraries using it' })).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Activity' })).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Releases' })).toBeVisible();
  await page.getByRole('tab', { name: 'Overview' }).click();
  await expect(page.locator('[data-owner-only]')).toContainText('Only an Owner can publish');
  await expect(page.getByRole('button', { name: /^Publish/ })).toBeHidden();
  await expect(page.locator('[data-error]:not([hidden])')).toHaveCount(0);

  // An Author may leave, as anyone with a role may.
  await page.getByRole('tab', { name: 'People' }).click();
  await page.getByRole('button', { name: 'Leave this repository' }).click();
  await expect.poll(async () => (await ok(author.api.GET('/me'))).memberships.length).toBe(0);
  await context.close();
});

test('an Owner makes a library link on the Libraries using it tab', async ({ browser }) => {
  const { owner, repository } = await repositoryWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await page.getByRole('tab', { name: 'Libraries using it' }).click();
  const links = page.locator('[data-library-links-slot] [data-tenant-invite-links]');

  await expect(links.locator('[data-role-field]')).toBeHidden();
  await links.getByRole('button', { name: 'Make a link' }).click();
  await expect(links.getByLabel('Library invite link')).toBeVisible();
  await expect(links).toContainText('open to whoever uses it first');
  await expect(links.locator('[data-list] > li').first()).toContainText('Library link');

  const [made] = (await invitesOf(owner, repository.id)).items;

  expect([made?.kind, made?.role, made?.max_uses]).toEqual(['library_access', null, 1]);
  await context.close();
});

test('in a library: an Owner has People with links; an Author may leave and has nothing else', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const author = await newUser('author');
  const library = await newLibrary(owner.api, `Table ${crypto.randomUUID().slice(0, 8)}`);

  await addMember(owner, library.id, author, 'author');

  const asOwner = await signedInPage(browser, owner.subject);

  const card = await openLibrary(asOwner.page, library);

  await card.getByRole('tab', { name: 'People' }).click();
  await expect(card.locator('[data-roles] strong').first()).toHaveText('Owner');
  await expect(card.locator('[data-roles] strong')).toHaveText(['Owner', 'Organizer', 'Author']);
  const links = card.locator('[data-tenant-invite-links]');

  await expect(links).toBeVisible();
  await links.getByRole('button', { name: 'Make a link' }).click();
  await expect(links.getByLabel('Author invite link')).toBeVisible();
  await expect(links).toContainText('becomes an Author of this library');
  await asOwner.context.close();

  const asAuthor = await signedInPage(browser, author.subject);

  const mine = await openLibrary(asAuthor.page, library);

  await expect(mine).toContainText('Author');
  await expect(mine.locator('[data-tenant-invite-links]')).toHaveCount(0);
  await mine.getByRole('tab', { name: 'People' }).click();
  await expect(mine.getByRole('button', { name: 'Leave this library' })).toBeVisible();
  await asAuthor.context.close();
});

test('People with its links panel fits a phone', async ({ browser }) => {
  const { owner, repository } = await repositoryWorld();
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 800 },
  });

  await openPeople(page, repository.slug);
  await page.getByRole('button', { name: 'Make a link' }).click();
  await expect(page.getByLabel('Author invite link')).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );

  expect(overflow).toBeLessThanOrEqual(0);
  await context.close();
});
