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

// ADR 0434, RFC 0051 H3: a protected repository. The launcher sets PUBLIC_REPOSITORIES_ENABLED for
// this suite (playwright.real-api.config.ts). Every test works in names of its own (a tag in each),
// since the listing is the whole deployment's.

const WORDS_NEVER_ON_SCREEN = /tenant|grant|subscri|flatten|\bsource/i;

const dialog = (page: Page) => page.locator('[data-visibility-dialog]');
const card = (page: Page) => page.locator('[data-visibility]');

async function copyInto(api: Api, tenantId: string, repositoryId: string) {
  await ok(
    api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: tenantId, repository_id: repositoryId } },
      body: {},
    }),
  );
}

// A is a private repository with an item and a stat group, published once.
async function world(prefix: string) {
  const owner = await newUser(`${prefix}-owner`, ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const a = await newRepository(owner.api, `Armoury ${tag}`);

  await addItem(owner.api, a.id, 'Longsword', `longsword-${tag}`);
  await addStatGroup(owner.api, a.id, 'Abilities', ['Strength']);
  await publish(owner.api, a.id);

  return { owner, tag, a };
}

async function makeProtected(api: Api, repositoryId: string) {
  await ok(
    api.PUT('/tenants/{tenant_id}/protected', {
      params: { path: { tenant_id: repositoryId } },
      body: { breaking: false, acknowledge_breaking: true, acknowledge_revokes: false },
    }),
  );
}

// A repository built on A: invited by A's Owner, a copy of A, and an item of its own.
async function bridgeOf(owner: Api, a: { id: string }, name: string, ownerOfA?: Api) {
  const b = await newRepository(owner, name);

  await invite(ownerOfA ?? owner, a.id, b.id);
  await copyInto(owner, b.id, a.id);
  await addItem(owner, b.id, `${name} Blade`);

  return b;
}

test('an Owner makes a repository protected, a repository built on it goes public over it, and a library holds it through that one', async ({
  browser,
}) => {
  test.slow();
  const { owner, tag, a } = await world('protect');
  // The repository built on it exists before the page is opened, which lists the repositories it knows.
  const b = await bridgeOf(owner.api, a, `Bridge ${tag}`);
  const { page, context } = await signedInPage(browser, owner.subject);

  // Making it protected: the dialog says what it does, asks for no summary and no terms line, and
  // makes a release with the flip.
  await page.goto(`/studio/?repository=${a.slug}`);
  await expect(card(page).locator('[data-visibility-state]')).toHaveText('Private');
  await expect(card(page).getByRole('button', { name: 'Make protected…' })).toBeVisible();
  await card(page).getByRole('button', { name: 'Make protected…' }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page).locator('[data-vis-title]')).toHaveText(`Make ${a.name} protected`);
  await expect(dialog(page).locator('[data-vis-lines]')).toContainText(
    'nobody copies it on its own',
  );
  await expect(dialog(page).getByRole('textbox', { name: /^Summary/ })).toBeHidden();
  await expect(
    dialog(page).getByRole('checkbox', { name: /^I have the right to publish/ }),
  ).toBeHidden();
  await expect(dialog(page).getByRole('textbox', { name: 'Label' })).toBeVisible();
  expect(await dialog(page).innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);
  await dialog(page).getByRole('button', { name: 'Make protected and publish release' }).click();
  await expect(dialog(page)).toBeHidden();
  await expect(card(page).locator('[data-visibility-state]')).toHaveText('Protected');
  await expect(card(page)).toContainText('Not on Discover, and not copied on its own');
  await expect(card(page).getByRole('button', { name: 'Make public…' })).toBeVisible();
  await expect(card(page).getByRole('button', { name: 'Make private…' })).toBeVisible();

  // The repository built on it takes the release the flip made, and its dialog of making it public
  // lists A as protected, with both choices, and nothing stands in the way: a protected repository is
  // reached.
  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/updates', {
      params: { path: { tenant_id: b.id, repository_id: a.id } },
      body: { actions: [] },
    }),
  );

  await page.goto(`/studio/?repository=${b.slug}`);
  await card(page).getByRole('button', { name: 'Make public…' }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page).locator('[data-vis-blockers]')).toBeHidden();

  const built = dialog(page).locator('[data-vis-built-on]');

  await expect(built).toContainText(a.name);
  await expect(built).toContainText('Protected');
  await expect(built.getByRole('radio', { name: 'Keep separate and visible' })).toBeChecked();
  await expect(built.getByRole('radio', { name: 'Include in this repository' })).toBeVisible();
  await expect(built).toContainText(`${a.name} stays a protected repository of its own`);
  await dialog(page)
    .getByRole('textbox', { name: /^Summary/ })
    .fill(`A bridge ${tag}`);
  await dialog(page)
    .getByRole('checkbox', { name: /^I have the right to publish this repository./ })
    .check();
  await dialog(page).getByRole('button', { name: 'Make public and publish release' }).click();
  await expect(dialog(page)).toBeHidden();
  await expect(card(page).locator('[data-visibility-state]')).toHaveText('Public');

  // A visitor does not find A: not on Discover, and its address is the page of a repository that
  // cannot be opened. B is open, and its page does not say it is built on a protected repository.
  const visitor = await newUser('protect-visitor', ['tenant_creator']);
  const library = await newLibrary(visitor.api, `Table ${tag}`);
  const guest = await signedInPage(browser, visitor.subject);

  await guest.page.goto(`/discover/?q=${a.name}`);
  await expect(guest.page.locator('[data-results] > li')).toHaveCount(0);
  await guest.page.goto(`/discover/?repository=${a.id}`);
  await expect(guest.page.getByText('This repository cannot be opened.')).toBeVisible();
  await guest.page.goto(`/discover/?repository=${b.id}`);
  await expect(guest.page.locator('[data-storefront]')).toBeVisible();
  expect(await guest.page.locator('[data-storefront]').innerText()).not.toContain(a.name);
  expect(
    (
      await visitor.api.GET('/repositories/{repository_id}/profile', {
        params: { path: { repository_id: a.id } },
      })
    ).response.status,
  ).toBe(404);

  // The library copies B and gets A with it, as a step of that copy.
  await copyInto(visitor.api, library.id, b.id);

  const alone = await visitor.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
    params: { path: { tenant_id: library.id, repository_id: a.id } },
    body: {},
  });

  expect(alone.response.status).toBe(409);

  // Shelf: A is there with a Protected pill and no name, cannot be copied on its own, and the
  // library's other repository is as ever.
  await guest.page.goto(`/repositories/?tenant=${library.slug}`);

  const held = guest.page.getByRole('listitem').filter({ hasText: 'A protected repository' });

  await expect(held).toBeVisible();
  await expect(held).toContainText('Protected');
  await expect(guest.page.getByRole('listitem').filter({ hasText: b.name })).toBeVisible();
  expect(await held.innerText()).not.toContain(a.name);
  await held.getByRole('link', { name: 'A protected repository' }).click();
  await expect(guest.page.locator('[data-protected-note]')).toContainText(
    'cannot be copied on its own',
  );
  await expect(guest.page.locator('[data-actions]')).toBeHidden();
  await expect(guest.page.locator('[data-more]')).toBeHidden();
  await expect(guest.page.getByRole('link', { name: 'Check for updates' })).toBeVisible();
  expect(await guest.page.locator('main').innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);

  await context.close();
  await guest.context.close();
});

test('an Owner of a protected repository says stay hidden, and a repository built on it is left with include', async ({
  browser,
}) => {
  test.slow();
  const { owner, tag, a } = await world('hidden');

  await makeProtected(owner.api, a.id);

  const other = await newUser('hidden-other', ['tenant_creator']);
  const c = await bridgeOf(other.api, a, `Other ${tag}`, owner.api);
  const ownerPage = await signedInPage(browser, owner.subject);

  // The terms card: Open to begin with, and the switches under the presets.
  await ownerPage.page.goto(`/studio/?repository=${a.slug}`);
  await ownerPage.page.getByRole('tab', { name: 'Profile' }).click();

  const terms = ownerPage.page.locator('[data-terms-card]');

  await expect(terms).toContainText('How repositories built on this one may use it');
  await expect(terms.getByRole('radio', { name: /^Open/ })).toBeChecked();
  await expect(terms.getByRole('radio', { name: /^Stay hidden/ })).not.toBeChecked();
  await expect(terms.getByRole('checkbox', { name: 'May be shown' })).toBeChecked();
  await expect(terms.getByRole('checkbox', { name: 'May be included' })).toBeChecked();
  expect(await terms.innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);

  await terms.getByRole('radio', { name: /^Stay hidden/ }).check();
  await expect(terms.locator('[data-terms-status]')).toHaveText('Saved.');
  await expect(terms.getByRole('checkbox', { name: 'May be shown' })).not.toBeChecked();
  await expect(terms.getByRole('checkbox', { name: 'May be included' })).toBeChecked();
  await expect(terms.locator('[data-terms-shown-line]')).toContainText('You did not allow it');
  expect(
    (
      await ok(
        owner.api.GET('/tenants/{tenant_id}/profile', { params: { path: { tenant_id: a.id } } }),
      )
    ).terms,
  ).toEqual({
    may_be_included: true,
    is_default: false,
    may_be_shown: false,
    may_be_shown_is_default: false,
    may_be_hidden: true,
    may_be_hidden_is_default: true,
  });

  // The other repository's Built on card keeps what it has chosen, and says why it is not offered
  // the choice it does not have; what is left is include.
  const otherPage = await signedInPage(browser, other.subject);

  await otherPage.page.goto(`/studio/?repository=${c.slug}`);
  await otherPage.page.getByRole('tab', { name: 'Built on' }).click();

  const row = otherPage.page.locator('[data-built-on-list] > li').filter({ hasText: 'Armoury' });

  await expect(row.locator('[data-inclusion-not-offered]')).toContainText('You cannot keep');
  await expect(row.locator('[data-inclusion-not-offered]')).toContainText(
    'Include it in this repository instead',
  );
  await row.getByRole('radio', { name: 'Include in this repository' }).check();
  await expect(row.locator('[data-inclusion-status]')).toHaveText('Saved.');
  expect(await row.innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);

  // And back: it cannot choose to show it again while A says no, and the words say so.
  await row.getByRole('radio', { name: 'Keep separate and visible' }).check();
  await expect(row.locator('[data-inclusion-status]')).toContainText('cannot be kept separate');
  await expect(row.getByRole('radio', { name: 'Include in this repository' })).toBeChecked();

  await ownerPage.context.close();
  await otherPage.context.close();
});

test('a protected repository with a public repository built on it says what stands in the way of making it private', async ({
  browser,
}) => {
  test.slow();
  const { owner, tag, a } = await world('private');

  await makeProtected(owner.api, a.id);

  const b = await bridgeOf(owner.api, a, `Bridge ${tag}`);

  await ok(
    owner.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: b.id } },
      body: {
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
        accept_terms: true,
        summary: `A bridge ${tag}`,
      },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${a.slug}`);
  await card(page).getByRole('button', { name: 'Make private…' }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page).locator('[data-vis-blockers]')).toContainText(
    `${b.name} is built on this repository and others can copy it.`,
  );
  await expect(
    dialog(page).getByRole('link', { name: `Open ${b.name} to make it private` }),
  ).toHaveAttribute('href', `/studio/?repository=${b.id}`);
  await expect(dialog(page).getByRole('button', { name: 'Make private' })).toBeDisabled();
  expect(await dialog(page).innerText()).not.toMatch(WORDS_NEVER_ON_SCREEN);
  await context.close();
});

test('on a phone, the card, the dialog and the terms are one column and everything pressed is big enough', async ({
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

  await page.goto(`/studio/?repository=${a.slug}`);
  await expect(card(page).getByRole('button', { name: 'Make protected…' })).toBeVisible();
  expect(
    (await card(page).getByRole('button', { name: 'Make protected…' }).boundingBox())?.height ?? 0,
  ).toBeGreaterThanOrEqual(44);
  expect(await noScroll()).toBeLessThanOrEqual(0);

  await card(page).getByRole('button', { name: 'Make protected…' }).click();
  await expect(dialog(page)).toBeVisible();

  const box = await dialog(page).boundingBox();

  expect(box).not.toBeNull();
  expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= 375).toBe(true);
  expect(await noScroll()).toBeLessThanOrEqual(0);
  await dialog(page).getByRole('button', { name: 'Make protected and publish release' }).click();
  await expect(card(page).locator('[data-visibility-state]')).toHaveText('Protected');
  for (const name of ['Make public…', 'Make private…']) {
    expect(
      (await card(page).getByRole('button', { name }).boundingBox())?.height ?? 0,
    ).toBeGreaterThanOrEqual(44);
  }

  await page.getByRole('tab', { name: 'Profile' }).click();

  const terms = page.locator('[data-terms-card]');

  await expect(terms).toBeVisible();
  for (const label of await terms.locator('label.field-row').all()) {
    expect((await label.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(await noScroll()).toBeLessThanOrEqual(0);

  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/updates', {
      params: { path: { tenant_id: b.id, repository_id: a.id } },
      body: { actions: [] },
    }),
  );
  await page.goto(`/studio/?repository=${b.slug}`);
  await card(page).getByRole('button', { name: 'Make public…' }).click();
  await expect(dialog(page)).toBeVisible();
  for (const label of ['Keep separate and visible', 'Include in this repository']) {
    const target = dialog(page).locator('label.field-row').filter({ hasText: label });

    expect((await target.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(await noScroll()).toBeLessThanOrEqual(0);
  await context.close();
});
