import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  addItem,
  addStatGroup,
  invite,
  newLibrary,
  newRepository,
  newUser,
  publish,
  signedInPage,
} from './support';

// ADR 0431, RFC 0051 H1: a repository includes one it is built on in its release. The launcher sets
// PUBLIC_REPOSITORIES_ENABLED for this suite (playwright.real-api.config.ts).

const WORDS_NEVER_ON_SCREEN = /tenant|grant|subscri|flatten|\bsource/i;
const LICENCE = { label: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' };

const dialog = (page: Page) => page.locator('[data-visibility-dialog]');

async function copyInto(api: Api, tenantId: string, repositoryId: string) {
  await ok(
    api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: tenantId, repository_id: repositoryId } },
      body: {},
    }),
  );
}

async function setTerms(api: Api, repositoryId: string, may: boolean | null) {
  await ok(
    api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repositoryId } },
      body: { terms: { may_be_included: may } },
    }),
  );
}

// A is a private repository with a licence, an item and a stat group; B is built on it (an
// invitation, and a copy), with an item of its own on top; one Owner owns both unless said.
async function world(prefix: string) {
  const owner = await newUser(`${prefix}-owner`, ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const a = await newRepository(owner.api, `Armoury ${tag}`);

  await addItem(owner.api, a.id, 'Longsword', `longsword-${tag}`);
  await addStatGroup(owner.api, a.id, 'Abilities', ['Strength']);
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: a.id } },
      body: { licence: LICENCE },
    }),
  );
  await publish(owner.api, a.id);

  return { owner, tag, a };
}

async function bridgeOf(owner: Api, a: { id: string }, name: string, ownerOfA?: Api) {
  const b = await newRepository(owner, name);

  await invite(ownerOfA ?? owner, a.id, b.id);
  await copyInto(owner, b.id, a.id);
  await addItem(owner, b.id, `${name} Blade`);

  return b;
}

test('an Owner includes a private repository, makes the repository public, and a library copies it without ever reading the other', async ({
  browser,
}) => {
  test.slow();
  const { owner, tag, a } = await world('include');
  const b = await bridgeOf(owner.api, a, `Bridge ${tag}`);
  const { page, context } = await signedInPage(browser, owner.subject);

  // The Built on tab says how each repository is carried, with what each choice does.
  await page.goto(`/repositories/?repository=${b.slug}`);
  await page.getByRole('tab', { name: 'Built on' }).click();

  const row = page.locator('[data-built-on-list] > li').filter({ hasText: a.name });

  await expect(row).toBeVisible();
  await expect(
    row.getByRole('group', { name: 'How is it carried in this repository?' }),
  ).toBeVisible();
  await expect(row.getByRole('radio', { name: 'Keep separate and visible' })).toBeChecked();
  await expect(row.getByRole('radio', { name: 'Include in this repository' })).not.toBeChecked();
  await expect(row).toContainText(`${a.name} stays a repository of its own`);
  // Nothing is said about changing it before a release carried it.
  await expect(row).not.toContainText('breaking release');

  // Making it public: it is built on a private repository, so the dialog says so, and offers to
  // include it instead, in a list with the choice for each.
  await page.goto(`/repositories/?repository=${b.slug}`);
  await page.locator('[data-visibility]').getByRole('button', { name: 'Make public…' }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page).locator('[data-vis-blockers]')).toContainText(`${a.name} is private.`);
  await expect(dialog(page).locator('[data-vis-blockers]')).toContainText(
    'Or include it in this repository, below.',
  );
  await expect(dialog(page).locator('[data-vis-built-on]')).toContainText(
    'How this repository carries what it is built on',
  );
  await expect(dialog(page).locator('[data-vis-built-on]')).toContainText('Private');
  expect(await dialog(page).innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);

  await dialog(page).getByRole('radio', { name: 'Include in this repository' }).check();
  // Choosing saves it, and the dialog reads again: nothing stands in the way now.
  await expect(dialog(page).locator('[data-vis-blockers]')).toBeHidden();
  await expect(
    dialog(page).getByRole('radio', { name: 'Include in this repository' }),
  ).toBeChecked();
  await expect(dialog(page).locator('[data-vis-built-on]')).toContainText(
    `The entries of ${a.name} become this repository’s own`,
  );

  await dialog(page)
    .getByRole('textbox', { name: /^Summary/ })
    .fill(`A bridge ${tag}`);
  await dialog(page)
    .getByRole('checkbox', { name: /^I have the right to publish this repository./ })
    .check();
  await dialog(page).getByRole('button', { name: 'Make public and publish release' }).click();
  await expect(dialog(page)).toBeHidden();
  await expect(page.locator('[data-visibility-state]')).toHaveText('Public');

  // After a release carried the choice, changing it says what it costs.
  await page.getByRole('tab', { name: 'Built on' }).click();
  await expect(row.getByRole('radio', { name: 'Include in this repository' })).toBeChecked();
  await expect(row).toContainText('Changing how this is included makes a breaking release.');

  // The profile: the terms of this repository for what is built on it, and what it includes.
  await page.getByRole('tab', { name: 'Profile' }).click();
  await expect(page.locator('[data-terms-card]')).toContainText(
    'How repositories built on this one may use it',
  );
  const facts = page.locator('[data-profile-preview] [data-preview-facts]');

  await expect(facts.getByText('Includes content from', { exact: true })).toBeVisible();
  await expect(facts).toContainText(`${a.name}, ${LICENCE.label}`);

  // A second user finds it on Discover; its page names what it includes, with the licence.
  const visitor = await newUser('include-visitor', ['tenant_creator']);
  const library = await newLibrary(visitor.api, `Table ${tag}`);
  const guest = await signedInPage(browser, visitor.subject);

  await guest.page.goto(`/discover/?repository=${b.id}`);
  await expect(guest.page.locator('[data-storefront]')).toBeVisible();

  const includes = guest.page.locator('[data-includes-section]');

  await expect(includes).toBeVisible();
  await expect(includes).toContainText(`Includes content from ${a.name}, ${LICENCE.label}`);
  await expect(includes.getByRole('link', { name: LICENCE.label })).toHaveAttribute(
    'href',
    LICENCE.url,
  );
  expect(await guest.page.locator('[data-storefront]').innerText()).not.toMatch(
    WORDS_NEVER_ON_SCREEN,
  );

  // It copies, with no access to the repository it includes, and holds the rows as the bridge's.
  await copyInto(visitor.api, library.id, b.id);

  const items = await ok(
    visitor.api.GET('/tenants/{tenant_id}/items', {
      params: { path: { tenant_id: library.id } },
    }),
  );

  expect(items.items.map((item) => item.title).sort()).toEqual([
    `Bridge ${tag} Blade`,
    'Longsword',
  ]);

  const held = await ok(
    visitor.api.GET('/tenants/{tenant_id}/repositories', {
      params: { path: { tenant_id: library.id } },
    }),
  );

  expect(held.items.map((entry) => entry.repository.name)).toEqual([b.name]);

  const closed = await visitor.api.GET(
    '/tenants/{tenant_id}/repositories/{repository_id}/entities',
    {
      params: { path: { tenant_id: library.id, repository_id: a.id } },
    },
  );

  expect(closed.response.status).toBe(404);
  await context.close();
  await guest.context.close();
});

test('a repository that is not allowed to include another is not offered it, and says why', async ({
  browser,
}) => {
  test.slow();
  const { owner, tag, a } = await world('refused');
  const other = await newUser('refused-other', ['tenant_creator']);
  const c = await bridgeOf(other.api, a, `Other ${tag}`, owner.api);
  const { page, context } = await signedInPage(browser, other.subject);

  await page.goto(`/repositories/?repository=${c.slug}`);
  await page.getByRole('tab', { name: 'Built on' }).click();

  const row = page.locator('[data-built-on-list] > li').filter({ hasText: a.name });

  await expect(row.getByRole('radio', { name: 'Keep separate and visible' })).toBeChecked();
  await expect(row.getByRole('radio', { name: 'Include in this repository' })).toHaveCount(0);
  await expect(row.locator('[data-inclusion-not-offered]')).toContainText(
    `You cannot include ${a.name} here`,
  );
  await expect(row.locator('[data-inclusion-not-offered]')).toContainText(
    'Ask its Owner to turn on “May be included”',
  );
  expect(await row.innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);
  expect(
    (
      await ok(
        other.api.GET('/tenants/{tenant_id}/flip-check', { params: { path: { tenant_id: c.id } } }),
      )
    ).built_on[0]?.includable,
  ).toEqual({ allowed: false, by: null });
  await context.close();

  // Its Owner says yes, and it is offered; then takes the yes back between the page and the click:
  // the refusal is shown in words and the choice goes back to what it was.
  await setTerms(owner.api, a.id, true);

  const again = await signedInPage(browser, other.subject);

  await again.page.goto(`/repositories/?repository=${c.slug}`);
  await again.page.getByRole('tab', { name: 'Built on' }).click();

  const offered = again.page.locator('[data-built-on-list] > li').filter({ hasText: a.name });

  await expect(offered.getByRole('radio', { name: 'Include in this repository' })).toBeVisible();
  await setTerms(owner.api, a.id, false);
  await offered.getByRole('radio', { name: 'Include in this repository' }).check();
  await expect(offered.locator('[data-inclusion-status]')).toContainText(
    `${a.name} cannot be included here: its Owner has not allowed it`,
  );
  await expect(offered.getByRole('radio', { name: 'Keep separate and visible' })).toBeChecked();
  expect(
    (
      await ok(
        other.api.GET('/tenants/{tenant_id}/repositories', {
          params: { path: { tenant_id: c.id } },
        }),
      )
    ).items[0]?.inclusion,
  ).toBe('show');
  await again.context.close();
});

test('an Owner changes what repositories built on a repository may do with it, and a member reads it', async ({
  browser,
}) => {
  test.slow();
  const { owner, a } = await world('terms');
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/repositories/?repository=${a.slug}`);
  await page.getByRole('tab', { name: 'Profile' }).click();

  const card = page.locator('[data-terms-card]');
  const include = card.getByRole('checkbox', { name: 'May be included' });

  await expect(card).toContainText('How repositories built on this one may use it');
  await expect(include).not.toBeChecked();
  await expect(card.locator('[data-terms-line]')).toContainText(
    'a private repository may not be included',
  );
  await include.check();
  await expect(card.locator('[data-terms-status]')).toHaveText('Saved.');
  await expect(card.locator('[data-terms-line]')).toContainText('You allowed it.');
  expect(
    (
      await ok(
        owner.api.GET('/tenants/{tenant_id}/profile', { params: { path: { tenant_id: a.id } } }),
      )
    ).terms,
  ).toEqual({
    may_be_included: true,
    is_default: false,
    may_be_shown: true,
    may_be_shown_is_default: true,
    may_be_hidden: true,
    may_be_hidden_is_default: true,
  });

  // An Author reads it and cannot change it.
  const author = await newUser('terms-author');

  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: a.id } },
      body: { user_id: author.me.id, role: 'author' },
    }),
  );

  const reader = await signedInPage(browser, author.subject);

  await reader.page.goto(`/repositories/?repository=${a.slug}`);
  await reader.page.getByRole('tab', { name: 'Profile' }).click();
  await expect(reader.page.locator('[data-terms-card]')).toContainText('You allowed it.');
  await expect(
    reader.page.locator('[data-terms-card]').getByRole('checkbox', { name: 'May be included' }),
  ).toBeDisabled();
  await expect(reader.page.locator('[data-terms-owner-only]')).toHaveText(
    'Only an Owner can change this.',
  );
  await reader.context.close();
  await context.close();
});

test('on a phone, the choice and the dialog are one column and everything pressed is big enough', async ({
  browser,
}) => {
  test.slow();
  const { owner, tag, a } = await world('phone');
  const b = await bridgeOf(owner.api, a, `Bridge ${tag}`);
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });
  const noScroll = () =>
    page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );

  await page.goto(`/repositories/?repository=${b.slug}`);
  await page.getByRole('tab', { name: 'Built on' }).click();

  const row = page.locator('[data-built-on-list] > li').filter({ hasText: a.name });

  await expect(row.getByRole('radio', { name: 'Include in this repository' })).toBeVisible();
  for (const label of ['Keep separate and visible', 'Include in this repository']) {
    const target = row.locator('label.field-row').filter({ hasText: label });

    expect((await target.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(await noScroll()).toBeLessThanOrEqual(0);

  await page.getByRole('tab', { name: 'Profile' }).click();
  await expect(page.locator('[data-terms-card]')).toBeVisible();
  expect(
    (await page.locator('[data-terms-card] label.field-row').first().boundingBox())?.height ?? 0,
  ).toBeGreaterThanOrEqual(44);
  expect(await noScroll()).toBeLessThanOrEqual(0);

  await page.goto(`/repositories/?repository=${b.slug}`);
  await page.locator('[data-visibility]').getByRole('button', { name: 'Make public…' }).click();
  await expect(dialog(page)).toBeVisible();

  const box = await dialog(page).boundingBox();

  expect(box).not.toBeNull();
  expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= 375).toBe(true);
  for (const label of ['Keep separate and visible', 'Include in this repository']) {
    const target = dialog(page).locator('label.field-row').filter({ hasText: label });

    expect((await target.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(await noScroll()).toBeLessThanOrEqual(0);
  await context.close();
});
