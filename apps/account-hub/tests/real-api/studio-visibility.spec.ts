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

// ADR 0290: Studio's visibility switch. The launcher sets PUBLIC_REPOSITORIES_ENABLED for this suite
// (playwright.real-api.config.ts): without it the API answers that public repositories are not
// available, and the card is not shown.

const dialog = (page: Page) => page.locator('[data-visibility-dialog]');
const card = (page: Page) => page.locator('[data-visibility]');
const state = (page: Page) => page.locator('[data-visibility-state]');
const summary = (page: Page) => dialog(page).getByRole('textbox', { name: /^Summary/ });

async function overview(page: Page, slug: string) {
  await page.goto(`/studio/?repository=${slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
}

async function profileOf(api: Api, repositoryId: string) {
  return ok(
    api.GET('/tenants/{tenant_id}/profile', { params: { path: { tenant_id: repositoryId } } }),
  );
}

async function checkOf(api: Api, repositoryId: string) {
  return ok(
    api.GET('/tenants/{tenant_id}/flip-check', { params: { path: { tenant_id: repositoryId } } }),
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

// A private repository with something in it, and a library invited to it.
async function world() {
  const owner = await newUser('owner', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await addItem(owner.api, repository.id, 'Owlbear');

  const library = await newLibrary(owner.api, `Table ${tag}`);

  await invite(owner.api, repository.id, library.id);

  return { owner, repository, library, tag };
}

test('a repository goes public through the dialog, and private again', async ({ browser }) => {
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(card(page)).toBeVisible();
  await expect(state(page)).toHaveText('Private');
  await expect(card(page).getByRole('button', { name: 'Make public…' })).toBeVisible();

  // What it will do, before it does it.
  await card(page).getByRole('button', { name: 'Make public…' }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(
    dialog(page).getByRole('heading', { name: `Make ${repository.name} public` }),
  ).toBeVisible();
  await expect(dialog(page)).toContainText('publishes a release');
  await expect(dialog(page)).toContainText('what you edit between two releases is not seen');
  await expect(dialog(page)).toContainText(
    "1 library has an invitation and is told when you publish: each one's Owners and Organizers get a notification.",
  );
  await expect(dialog(page)).toContainText('includes text marked GM only');
  await expect(dialog(page)).toContainText(
    'Libraries that copy it keep their copies, whatever you do to this repository later.',
  );
  expect(await dialog(page).innerText()).not.toMatch(/tenant|grant|subscri/i);

  // The three previews, showcase chosen.
  const radios = dialog(page).getByRole('radio');

  await expect(radios).toHaveCount(3);
  await expect(
    dialog(page).getByRole('radio', {
      name: 'People can look at the entries you feature before copying.',
    }),
  ).toBeChecked();

  // A summary is required: asked for, and nothing is changed.
  await dialog(page).getByRole('button', { name: 'Make public and publish release' }).click();
  await expect(dialog(page).locator('[data-vis-error]')).toContainText('Write a summary');
  expect((await profileOf(owner.api, repository.id)).visibility).toBe('private');

  await summary(page).fill('Every beast  there is,\nwith its habits.');
  await dialog(page).getByRole('radio', { name: 'People can look at every entry.' }).check();
  await dialog(page)
    .getByRole('textbox', { name: /^Label/ })
    .fill('First public');
  await dialog(page).getByRole('button', { name: 'Make public and publish release' }).click();

  await expect(dialog(page)).toBeHidden();
  await expect(state(page)).toHaveText('Public');
  await expect(page.locator('[data-visibility-status]')).toHaveText(
    'Public. A release was published.',
  );
  await expect(card(page).getByRole('button', { name: 'Make private…' })).toBeVisible();
  // A public repository is made private, not unpublished.
  await expect(page.getByRole('button', { name: 'Publish a new release…' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Unpublish…' })).toBeHidden();

  const profile = await profileOf(owner.api, repository.id);

  expect(profile.visibility).toBe('public');
  expect(profile.preview).toBe('public');
  expect(profile.summary).toBe('Every beast there is, with its habits.');

  const releases = await ok(
    owner.api.GET('/tenants/{tenant_id}/releases', {
      params: { path: { tenant_id: repository.id } },
    }),
  );

  expect(releases.items.map((release) => release.label)).toContain('First public');

  // And back: nobody copied it by itself, so nobody loses anything and nothing is asked.
  await card(page).getByRole('button', { name: 'Make private…' }).click();
  await expect(
    dialog(page).getByRole('heading', { name: `Make ${repository.name} private` }),
  ).toBeVisible();
  await expect(dialog(page)).toContainText(
    'No library copied it by itself while it was public, so none loses anything.',
  );
  await expect(dialog(page)).toContainText(
    '1 library you invited keeps its access, and reads the repository as it is again, not its releases.',
  );
  await expect(dialog(page).locator('[data-vis-ack-row]')).toBeHidden();
  await dialog(page).getByRole('button', { name: 'Make private', exact: true }).click();

  await expect(dialog(page)).toBeHidden();
  await expect(state(page)).toHaveText('Private');
  await expect(page.locator('[data-visibility-status]')).toHaveText('Private again.');
  expect((await profileOf(owner.api, repository.id)).visibility).toBe('private');
  await context.close();
});

test('cancelling changes nothing', async ({ browser }) => {
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await card(page).getByRole('button', { name: 'Make public…' }).click();
  // It opens at its top, at the first field.
  await expect(summary(page)).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog(page)).toBeHidden();
  await expect(state(page)).toHaveText('Private');
  expect((await profileOf(owner.api, repository.id)).visibility).toBe('private');
  await context.close();
});

test('the summary on the profile is what the dialog starts with, and it has to fit', async ({
  browser,
}) => {
  const { owner, repository } = await world();

  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: { summary: 'Already written.', preview: 'off' },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await card(page).getByRole('button', { name: 'Make public…' }).click();
  await expect(summary(page)).toHaveValue('Already written.');
  await expect(
    dialog(page).getByRole('radio', { name: 'People see its summary and counts only.' }),
  ).toBeChecked();

  await summary(page).fill('x'.repeat(281));
  await expect(dialog(page).locator('[data-vis-summary-count]')).toHaveText('281 of 280');
  await dialog(page).getByRole('button', { name: 'Make public and publish release' }).click();
  await expect(dialog(page).locator('[data-vis-error]')).toContainText(
    'A summary is at most 280 characters. This one is 281.',
  );
  expect((await profileOf(owner.api, repository.id)).visibility).toBe('private');
  await context.close();
});

test('a repository built on a private one is blocked, in words, with a way on', async ({
  browser,
}) => {
  const { owner, repository, tag } = await world();
  const other = await newUser('upstream-owner', ['tenant_creator']);

  // Built on one the Owner owns, and on one somebody else owns.
  const core = await newRepository(owner.api, `Core ${tag}`);
  const theirs = await newRepository(other.api, `Theirs ${tag}`);

  await addItem(owner.api, core.id, 'Longsword');
  await addItem(other.api, theirs.id, 'Shield');
  await publish(owner.api, core.id);
  await publish(other.api, theirs.id);
  await invite(owner.api, core.id, repository.id);
  await invite(other.api, theirs.id, repository.id);
  await copyInto(owner.api, repository.id, core.id);
  await copyInto(owner.api, repository.id, theirs.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await card(page).getByRole('button', { name: 'Make public…' }).click();
  await expect(dialog(page).locator('[data-vis-blockers]')).toBeVisible();
  await expect(dialog(page).locator('[data-vis-blockers]')).toContainText(
    'Before you can make it public',
  );
  await expect(dialog(page).locator('[data-vis-blocker-list]')).toContainText(
    `${core.name} is not public.`,
  );
  await expect(dialog(page).locator('[data-vis-blocker-list]')).toContainText(
    `${theirs.name} is not public. This repository is built on it, so it has to be public first: ask its Owner to make it public.`,
  );

  // A link to the Studio page of the one the Owner owns, and none for the other.
  const link = dialog(page).getByRole('link', { name: `Open ${core.name} to make it public` });

  await expect(link).toHaveAttribute('href', `/studio/?repository=${core.id}`);
  await expect(dialog(page).getByRole('link')).toHaveCount(1);

  // Nothing can be sent while anything stands in the way.
  await expect(
    dialog(page).getByRole('button', { name: 'Make public and publish release' }),
  ).toBeDisabled();
  await expect(summary(page)).toBeHidden();

  // The link leads to the repository it names.
  await link.click();
  await expect(page.locator('[data-repository] h2[data-name]')).toHaveText(core.name);
  await context.close();
});

test('a repository that is behind what it is built on is told to take the release first', async ({
  browser,
}) => {
  const { owner, repository, tag } = await world();
  const core = await newRepository(owner.api, `Core ${tag}`);

  await addItem(owner.api, core.id, 'Longsword');
  await publish(owner.api, core.id);
  await invite(owner.api, core.id, repository.id);
  await copyInto(owner.api, repository.id, core.id);

  // The core goes public, and the repository is built on a public one, but has not taken its
  // newest release: the core makes another.
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: core.id } },
      body: {
        summary: 'The core rules',
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
      },
    }),
  );
  await addItem(owner.api, core.id, 'Dagger');
  await publish(owner.api, core.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await card(page).getByRole('button', { name: 'Make public…' }).click();
  await expect(dialog(page).locator('[data-vis-blocker-list]')).toContainText(
    `Take the new release of ${core.name} first: open Built on.`,
  );
  await expect(
    dialog(page).getByRole('button', { name: 'Make public and publish release' }),
  ).toBeDisabled();
  await context.close();
});

test('going private says how many libraries lose its updates, and asks first', async ({
  browser,
}) => {
  const { owner, repository } = await world();
  const copier = await newUser('copier', ['tenant_creator']);
  const copiers = await newLibrary(copier.api, `Copiers ${crypto.randomUUID().slice(0, 8)}`);

  await ok(
    owner.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repository.id } },
      body: {
        summary: 'Every beast',
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
      },
    }),
  );
  await copyInto(copier.api, copiers.id, repository.id);
  expect((await checkOf(owner.api, repository.id)).public_libraries).toBe(1);

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(state(page)).toHaveText('Public');
  await card(page).getByRole('button', { name: 'Make private…' }).click();
  await expect(dialog(page)).toContainText(
    '1 library copied it while it was public: it keeps what it copied and loses its updates.',
  );
  await expect(dialog(page)).toContainText(
    '1 library you invited keeps its access, and reads the repository as it is again, not its releases.',
  );

  // Cancel has the focus: this one cuts libraries off.
  await expect(dialog(page).getByRole('button', { name: 'Cancel' })).toBeFocused();

  // The last button asks for the acknowledgement, and changes nothing without it.
  await dialog(page).getByRole('button', { name: 'Make private', exact: true }).click();
  await expect(dialog(page).locator('[data-vis-error]')).toContainText('Say you understand');
  expect((await profileOf(owner.api, repository.id)).visibility).toBe('public');

  await dialog(page)
    .getByRole('checkbox', {
      name: 'I understand that 1 library will lose the updates of this repository and keep what it copied.',
    })
    .check();
  await dialog(page).getByRole('button', { name: 'Make private', exact: true }).click();

  await expect(dialog(page)).toBeHidden();
  await expect(state(page)).toHaveText('Private');
  await expect(page.locator('[data-visibility-status]')).toHaveText(
    'Private again. 1 library lost its updates and keeps what it copied.',
  );
  expect((await profileOf(owner.api, repository.id)).visibility).toBe('private');
  expect((await checkOf(owner.api, repository.id)).invited_libraries).toBe(1);
  await context.close();
});

test('a repository that public ones are built on cannot be made private, and the dialog names them', async ({
  browser,
}) => {
  const { owner, repository, tag } = await world();
  const bridge = await newRepository(owner.api, `Bridge ${tag}`);

  await addItem(owner.api, bridge.id, 'Hammer');
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repository.id } },
      body: {
        summary: 'Every beast',
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
      },
    }),
  );
  const other = await newUser('dependent-owner', ['tenant_creator']);
  const theirs = await newRepository(other.api, `Theirs ${tag}`);

  await addItem(other.api, theirs.id, 'Shield');
  await invite(owner.api, repository.id, bridge.id);
  await copyInto(owner.api, bridge.id, repository.id);
  await copyInto(other.api, theirs.id, repository.id);
  await ok(
    other.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: theirs.id } },
      body: {
        summary: 'Theirs',
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
      },
    }),
  );
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: bridge.id } },
      body: {
        summary: 'The bridge',
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
      },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await card(page).getByRole('button', { name: 'Make private…' }).click();
  await expect(dialog(page).locator('[data-vis-blockers]')).toContainText(
    'Before you can make it private',
  );
  await expect(dialog(page).locator('[data-vis-blocker-list]')).toContainText(
    `${bridge.name} is public and built on this repository. Make it private first`,
  );
  await expect(dialog(page).locator('[data-vis-blocker-list]')).toContainText(
    `${theirs.name} is public and built on this repository. It has to be private first, so that what it is built on can still be copied: ask its Owner to make it private.`,
  );

  // A link to the Studio page of the one the Owner owns, and none for the other.
  await expect(dialog(page).getByRole('link')).toHaveCount(1);
  await expect(
    dialog(page).getByRole('link', { name: `Open ${bridge.name} to make it private` }),
  ).toHaveAttribute('href', `/studio/?repository=${bridge.id}`);
  await expect(
    dialog(page).getByRole('button', { name: 'Make private', exact: true }),
  ).toBeDisabled();
  await context.close();
});

test('the card is not shown where the deployment has no public repositories', async ({
  browser,
}) => {
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.route('**/flip-check', async (route) => {
    const real = await (await route.fetch()).json();

    await route.fulfill({ json: { ...real, available: false } });
  });
  await overview(page, repository.slug);
  // The rest of the Overview is there, and the switch is not.
  await expect(page.getByRole('button', { name: 'Publish…', exact: true })).toBeVisible();
  await expect(card(page)).toBeHidden();
  await expect(page.getByRole('button', { name: /Make public/ })).toHaveCount(0);
  await context.close();
});

test('an Organizer has no switch', async ({ browser }) => {
  const { owner, repository } = await world();
  const organizer = await newUser('organizer');

  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: repository.id } },
      body: { user_id: organizer.me.id, role: 'orga' },
    }),
  );

  const { page, context } = await signedInPage(browser, organizer.subject);
  const asked: string[] = [];

  page.on('request', (request) => {
    if (request.url().includes('/flip-check')) asked.push(request.url());
  });
  await overview(page, repository.slug);
  await expect(
    page.getByText('Only an Owner can publish or unpublish a repository.'),
  ).toBeVisible();
  await expect(card(page)).toBeHidden();
  await expect(page.getByRole('button', { name: /Make (public|private)/ })).toHaveCount(0);
  expect(asked).toEqual([]);
  await context.close();
});

test('on a phone, both dialogs fit and everything pressed is big enough', async ({ browser }) => {
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  await overview(page, repository.slug);
  await card(page).scrollIntoViewIfNeeded();
  await card(page).getByRole('button', { name: 'Make public…' }).click();
  await expect(dialog(page)).toBeVisible();

  const fits = async () => {
    const box = await dialog(page).boundingBox();

    expect(box).not.toBeNull();
    expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= 375).toBe(true);
    expect((box?.y ?? -1) >= 0 && (box?.y ?? 0) + (box?.height ?? 0) <= 812).toBe(true);

    // Nothing in it is wider than the dialog, so nothing is cut off at the side.
    const overflow = await page.evaluate(() => {
      const element = document.querySelector<HTMLElement>('[data-visibility-dialog]');

      return element ? element.scrollWidth - element.clientWidth : 0;
    });

    expect(overflow).toBeLessThanOrEqual(0);

    const heights = await page.evaluate(() =>
      [
        ...document.querySelectorAll<HTMLElement>(
          '[data-visibility-dialog] button, [data-visibility-dialog] .field-row',
        ),
      ]
        .filter((element) => element.offsetParent !== null)
        .map((element) => Math.round(element.getBoundingClientRect().height)),
    );

    expect(heights.length).toBeGreaterThanOrEqual(2);
    expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  };

  await fits();

  // The last button is reached by scrolling inside the dialog, not off the screen.
  await dialog(page)
    .getByRole('button', { name: 'Make public and publish release' })
    .scrollIntoViewIfNeeded();
  await expect(
    dialog(page).getByRole('button', { name: 'Make public and publish release' }),
  ).toBeInViewport();
  await summary(page).fill('Every beast there is.');
  await dialog(page).getByRole('button', { name: 'Make public and publish release' }).click();
  await expect(state(page)).toHaveText('Public');

  await card(page).getByRole('button', { name: 'Make private…' }).click();
  await expect(dialog(page)).toBeVisible();
  await fits();
  await context.close();
});

test('if it became public under an open page, Unpublish is refused in the API’s words', async ({
  browser,
}) => {
  const { owner, repository } = await world();

  await publish(owner.api, repository.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(state(page)).toHaveText('Private');
  await expect(page.getByRole('button', { name: 'Unpublish…' })).toBeVisible();

  // Somebody else makes it public after the page was read.
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repository.id } },
      body: {
        summary: 'Every beast',
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
      },
    }),
  );
  await page.getByRole('button', { name: 'Unpublish…' }).click();
  await page
    .locator('[data-publish-dialog]')
    .getByRole('button', { name: 'Unpublish', exact: true })
    .click();
  await expect(page.locator('[data-publish-dialog] [data-dialog-error]')).toContainText(
    'Make this repository private first',
  );
  await expect(page.locator('[data-publish-dialog]')).toBeVisible();
  expect((await profileOf(owner.api, repository.id)).visibility).toBe('public');
  await context.close();
});
