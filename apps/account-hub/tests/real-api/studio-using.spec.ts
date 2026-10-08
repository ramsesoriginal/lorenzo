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

async function copyInto(api: Api, tenantId: string, repositoryId: string) {
  await ok(
    api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: tenantId, repository_id: repositoryId } },
      body: {},
    }),
  );
}

async function stopInviting(api: Api, repositoryId: string, libraryId: string) {
  await ok(
    api.DELETE('/tenants/{tenant_id}/subscribers/{subscriber_tenant_id}', {
      params: { path: { tenant_id: repositoryId, subscriber_tenant_id: libraryId } },
    }),
  );
}

// A published repository with three libraries around it: one that copied it, one invited and not
// yet copied, and one that copied it and was then no longer invited. And an Organizer.
async function usingWorld() {
  const owner = await newUser('owner', ['tenant_creator']);
  const organizer = await newUser('organizer');
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: repository.id } },
      body: { user_id: organizer.me.id, role: 'orga' },
    }),
  );
  await addItem(owner.api, repository.id, 'Owlbear');
  await publish(owner.api, repository.id);

  const copied = await newLibrary(owner.api, `Copied ${tag}`);
  const waiting = await newLibrary(owner.api, `Waiting ${tag}`);
  const kept = await newLibrary(owner.api, `Kept ${tag}`);

  for (const library of [copied, waiting, kept]) await invite(owner.api, repository.id, library.id);

  await copyInto(owner.api, copied.id, repository.id);
  await copyInto(owner.api, kept.id, repository.id);
  await stopInviting(owner.api, repository.id, kept.id);

  return { owner, organizer, repository, copied, waiting, kept, tag };
}

async function openTab(page: Page, repositorySlug: string, tab: string) {
  await page.goto(`/studio/?repository=${repositorySlug}`);
  await page.getByRole('tab', { name: tab }).click();
}

function row(page: Page, name: string) {
  return page.locator('[data-using-list] > li').filter({ hasText: name });
}

test('Libraries using it: who is invited, who copied, and who kept a copy after the invitation went', async ({
  browser,
}) => {
  const { owner, repository, copied, waiting, kept } = await usingWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await openTab(page, repository.slug, 'Libraries using it');

  await expect(page.locator('[data-using-summary]')).toHaveText(
    '3 libraries and repositories have an invitation or a copy. 2 of them have copied it.',
  );
  await expect(row(page, copied.name)).toContainText('Copied');
  await expect(row(page, copied.name)).toContainText(
    /Invited \d{4}-\d{2}-\d{2}, copied \d{4}-\d{2}-\d{2}/,
  );
  await expect(row(page, waiting.name)).toContainText('Invited, not copied yet');
  await expect(row(page, kept.name)).toContainText('Not invited any more');
  await expect(row(page, kept.name)).toContainText('It keeps its copy and gets no more updates');

  // An Owner can stop an invitation that is there, and has nothing to stop for a copy that is not.
  await expect(row(page, copied.name).getByRole('button', { name: 'Stop inviting' })).toBeVisible();
  await expect(
    row(page, waiting.name).getByRole('button', { name: 'Stop inviting' }),
  ).toBeVisible();
  await expect(row(page, kept.name).getByRole('button', { name: 'Stop inviting' })).toBeHidden();
  await context.close();
});

test('an Owner invites a library by its id, and is told when it is not one', async ({
  browser,
}) => {
  const { owner, repository, tag } = await usingWorld();
  const another = await newLibrary(owner.api, `Another ${tag}`);
  const { page, context } = await signedInPage(browser, owner.subject);

  await openTab(page, repository.slug, 'Libraries using it');

  await page.getByLabel('Library id').fill('my-table');
  await page.getByRole('button', { name: 'Invite' }).click();
  await expect(page.locator('[data-invite-status]')).toContainText('not an id');

  await page.getByLabel('Library id').fill(another.id);
  await page.getByRole('button', { name: 'Invite' }).click();
  await expect(row(page, another.name)).toContainText('Invited, not copied yet');
  await expect(page.locator('[data-using-summary]')).toContainText('4 libraries and repositories');

  // An id that is not a library's is refused in the API's words.
  await page.getByLabel('Library id').fill('00000000-0000-4000-8000-000000000000');
  await page.getByRole('button', { name: 'Invite' }).click();
  await expect(page.locator('[data-invite-status]')).not.toHaveText('Inviting…');
  await expect(page.locator('[data-invite-status]')).toHaveClass(/error-text/);
  await context.close();
});

test('stopping an invitation says what it does first, tells the library, and leaves its copy', async ({
  browser,
}) => {
  const { owner, repository, copied } = await usingWorld();
  const { page, context, confirmations } = await signedInPage(browser, owner.subject);

  await openTab(page, repository.slug, 'Libraries using it');
  await row(page, copied.name).getByRole('button', { name: 'Stop inviting' }).click();

  expect(confirmations[0]).toContain(`Stop inviting “${copied.name}”?`);
  expect(confirmations[0]).toContain('What it copied stays with it');
  expect(confirmations[0].toLowerCase()).not.toContain('tenant');

  // It is still listed, as one that keeps its copy.
  await expect(row(page, copied.name)).toContainText('Not invited any more');
  await expect(row(page, copied.name).getByRole('button', { name: 'Stop inviting' })).toBeHidden();

  // The library was told, and its copy stayed.
  const notices = await ok(owner.api.GET('/me/notifications'));

  expect(notices.items.some((n) => n.type === 'repository_revoked')).toBe(true);
  const items = await ok(
    owner.api.GET('/tenants/{tenant_id}/items', { params: { path: { tenant_id: copied.id } } }),
  );

  expect(items.items.map((item) => item.title)).toContain('Owlbear');
  await context.close();
});

test('an Organizer reads who uses it and changes nothing', async ({ browser }) => {
  const { organizer, repository, copied } = await usingWorld();
  const { page, context } = await signedInPage(browser, organizer.subject);

  await openTab(page, repository.slug, 'Libraries using it');
  await expect(row(page, copied.name)).toContainText('Copied');
  await expect(page.getByRole('button', { name: 'Stop inviting' })).toHaveCount(0);
  await expect(page.getByLabel('Library id')).toBeHidden();
  await context.close();
});

test('Built on: what a repository copies from, with its updates waiting, and the screens to review them', async ({
  browser,
}) => {
  const owner = await newUser('builder', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const core = await newRepository(owner.api, `Core ${tag}`);
  const bridge = await newRepository(owner.api, `Bridge ${tag}`);
  const alone = await newRepository(owner.api, `Alone ${tag}`);
  const sword = await addItem(owner.api, core.id, 'Longsword');

  await publish(owner.api, core.id);
  await invite(owner.api, core.id, bridge.id);
  await copyInto(owner.api, bridge.id, core.id);

  // The core moves on after the bridge copied it.
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { tenant_id: core.id, entity_id: sword.entity_id } },
      body: { name: 'Longsword +1' },
    }),
  );
  await publish(owner.api, core.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await openTab(page, alone.slug, 'Built on');
  await expect(page.getByText('This repository is not built on another')).toBeVisible();
  await expect(page.getByText('ask its Owner to invite this one')).toBeVisible();

  await openTab(page, bridge.slug, 'Built on');

  const built = page.locator('[data-built-on-list] > li').filter({ hasText: core.name });

  await expect(built).toContainText('Update announced');
  await expect(built).toContainText(/copied \d{4}-\d{2}-\d{2}/);
  await expect(built.locator('[data-updates]')).toHaveText('Updates: 1 changed');

  // Review updates is Shelf's own screen, acting for this repository.
  await built.getByRole('link', { name: 'Review updates' }).click();
  await expect(page).toHaveURL(new RegExp(`tenant=${bridge.slug}.*updates=1`));
  await expect(page.getByRole('heading', { name: `Updates from ${core.name}` })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Changed (1)' })).toBeVisible();
  await expect(page.locator('#shelf-library option:checked')).toHaveText(
    `${bridge.name} (repository)`,
  );

  // And the repositories offered to it are Shelf's list for it.
  await page.goto(`/studio/?repository=${bridge.slug}`);
  await page.getByRole('tab', { name: 'Built on' }).click();
  await page.getByRole('link', { name: 'Repositories offered to this one' }).click();
  await expect(page).toHaveURL(new RegExp(`tenant=${bridge.slug}`));
  await expect(page.getByRole('link', { name: core.name })).toBeVisible();
  await context.close();
});

test('Activity: the repository’s log, for whoever works on it', async ({ browser }) => {
  const { owner, repository } = await usingWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await openTab(page, repository.slug, 'Activity');
  await expect(page.getByRole('heading', { name: 'Activity log' })).toBeVisible();
  // It was published, and libraries were invited to it.
  await expect(page.locator('[data-activity-log] [data-entries] li').first()).toBeVisible();
  await expect(page.locator('[data-activity-log]')).toContainText('repository.published');
  await context.close();
});

test('on a phone, the new tabs are one column and everything pressed is big enough', async ({
  browser,
}) => {
  const { owner, repository } = await usingWorld();
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  for (const tab of ['Libraries using it', 'Built on', 'Activity']) {
    await openTab(page, repository.slug, tab);
    await expect(page.getByRole('tab', { name: tab })).toHaveAttribute('aria-selected', 'true');

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );

    expect(overflow).toBeLessThanOrEqual(0);

    const heights = await page.evaluate(() =>
      [
        ...document.querySelectorAll<HTMLElement>(
          '[data-studio-panel] button, [data-studio-panel] .tab, [data-studio-panel] .btn, [data-studio-panel] .text-input, [data-studio-panel] .shelf-link',
        ),
      ]
        .filter((element) => element.offsetParent !== null)
        .map((element) => Math.round(element.getBoundingClientRect().height)),
    );

    expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  }

  await context.close();
});
