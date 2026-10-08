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

async function notices(api: Api, type: string): Promise<number> {
  const all = await ok(api.GET('/me/notifications'));

  return all.items.filter((n) => n.type === type).length;
}

// A draft repository with two libraries invited to it, and an Organizer.
async function draftWorld() {
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

  const first = await newLibrary(owner.api, `First ${tag}`);
  const second = await newLibrary(owner.api, `Second ${tag}`);

  await invite(owner.api, repository.id, first.id);
  await invite(owner.api, repository.id, second.id);

  return { owner, organizer, repository, first, second, tag };
}

async function overview(page: Page, slug: string) {
  await page.goto(`/studio/?repository=${slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
}

const dialog = (page: Page) => page.locator('[data-publish-dialog]');

test('publishing says what it will do first, and does nothing until it is confirmed', async ({
  browser,
}) => {
  const { owner, repository } = await draftWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(page.locator('[data-overview] [data-state]')).toHaveText('Draft');
  await page.getByRole('button', { name: 'Publish…', exact: true }).click();

  // What it will do, before it does it.
  await expect(
    dialog(page).getByRole('heading', { name: `Publish ${repository.name}` }),
  ).toBeVisible();
  await expect(dialog(page)).toContainText(
    "2 libraries have an invitation and are told when you publish: each one's Owners and Organizers get a notification.",
  );
  await expect(dialog(page)).toContainText('can look inside it, copy it and take its updates');
  await expect(dialog(page)).toContainText('Notes marked GM only are copied along');
  await expect(dialog(page)).toContainText('it sees when it next checks for updates');
  expect(await dialog(page).innerText()).not.toMatch(/tenant|grant|subscri/i);

  // Cancel changes nothing, and nobody is told.
  const before = await notices(owner.api, 'repository_published');

  await dialog(page).getByRole('button', { name: 'Cancel' }).click();
  await expect(dialog(page)).toBeHidden();
  await expect(page.locator('[data-overview] [data-state]')).toHaveText('Draft');
  expect(await notices(owner.api, 'repository_published')).toBe(before);

  // Confirm does it, and the libraries are told.
  await page.getByRole('button', { name: 'Publish…', exact: true }).click();
  await dialog(page).getByRole('button', { name: 'Publish and tell 2 libraries' }).click();
  await expect(page.locator('[data-overview] [data-state]')).toHaveText(
    /^Published \d{4}-\d{2}-\d{2}$/,
  );
  await expect(page.locator('[data-publish-status]')).toHaveText('Published.');
  await expect(page.locator('[data-live]')).toBeVisible();
  expect(await notices(owner.api, 'repository_published')).toBe(before + 2);
  await context.close();
});

test('a repository built on one that is not published is warned about before it is published', async ({
  browser,
}) => {
  const { owner, repository, tag } = await draftWorld();
  const core = await newRepository(owner.api, `Core ${tag}`);

  await addItem(owner.api, core.id, 'Longsword');
  await publish(owner.api, core.id);
  await invite(owner.api, core.id, repository.id);
  await copyInto(owner.api, repository.id, core.id);
  // The core is withdrawn again.
  await ok(
    owner.api.DELETE('/tenants/{tenant_id}/published', {
      params: { path: { tenant_id: core.id } },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await page.getByRole('button', { name: 'Publish…', exact: true }).click();
  await expect(dialog(page)).toContainText(
    `${core.name} is not published. A copy of this repository is refused until it is`,
  );
  await expect(dialog(page)).toContainText(`built on ${core.name}`);
  await expect(dialog(page)).toContainText('invitations are not passed on');
  await context.close();
});

test('telling libraries about an update is the same publish, said as what it is', async ({
  browser,
}) => {
  const { owner, repository } = await draftWorld();

  await publish(owner.api, repository.id);

  const before = await notices(owner.api, 'repository_updated');
  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(page.getByRole('button', { name: 'Publish…', exact: true })).toBeHidden();
  await page.getByRole('button', { name: 'Tell libraries about an update…' }).click();
  await expect(dialog(page)).toContainText('only says "look now"');
  await dialog(page).getByRole('button', { name: 'Tell 2 libraries' }).click();
  await expect(page.locator('[data-publish-status]')).toHaveText('Libraries were told.');
  expect(await notices(owner.api, 'repository_updated')).toBe(before + 2);
  await context.close();
});

test('unpublishing says what libraries lose and keep, sends nothing, and leaves their copies', async ({
  browser,
}) => {
  const { owner, repository, first } = await draftWorld();

  await publish(owner.api, repository.id);
  await copyInto(owner.api, first.id, repository.id);

  const told = await notices(owner.api, 'repository_updated');
  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await page.getByRole('button', { name: 'Unpublish…' }).click();
  await expect(dialog(page)).toContainText('It goes back to a draft.');
  await expect(dialog(page)).toContainText(
    '2 libraries have an invitation and can no longer look inside it, copy it or check for updates',
  );
  await expect(dialog(page)).toContainText(
    'What 1 library already copied stays with it, and nothing is deleted.',
  );
  await expect(dialog(page)).toContainText('Nobody is sent a message about it.');
  await dialog(page).getByRole('button', { name: 'Unpublish', exact: true }).click();

  await expect(page.locator('[data-overview] [data-state]')).toHaveText('Draft');
  await expect(page.locator('[data-publish-status]')).toHaveText(
    'Unpublished. It is a draft again.',
  );
  expect(await notices(owner.api, 'repository_updated')).toBe(told);

  // A library can no longer look inside it; the copy it made stays.
  const looked = await owner.api.GET('/tenants/{tenant_id}/repositories/{repository_id}/entities', {
    params: { path: { tenant_id: first.id, repository_id: repository.id } },
  });

  expect(looked.response.ok).toBe(false);

  const items = await ok(
    owner.api.GET('/tenants/{tenant_id}/items', { params: { path: { tenant_id: first.id } } }),
  );

  expect(items.items.map((item) => item.title)).toContain('Owlbear');
  await context.close();
});

test('an Organizer cannot publish, and is told who can', async ({ browser }) => {
  const { organizer, repository } = await draftWorld();
  const { page, context } = await signedInPage(browser, organizer.subject);

  await overview(page, repository.slug);
  await expect(page.getByRole('button', { name: /Publish|Unpublish|Tell libraries/ })).toHaveCount(
    0,
  );
  await expect(
    page.getByText('Only an Owner can publish or unpublish a repository.'),
  ).toBeVisible();
  await context.close();
});

test('the dialog is a real dialog: Escape closes it, and Cancel has the focus', async ({
  browser,
}) => {
  const { owner, repository } = await draftWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await page.getByRole('button', { name: 'Publish…', exact: true }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page).getByRole('button', { name: 'Cancel' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog(page)).toBeHidden();
  await expect(page.locator('[data-overview] [data-state]')).toHaveText('Draft');
  await context.close();
});

test('on a phone, the dialog fits and everything pressed is big enough', async ({ browser }) => {
  const { owner, repository } = await draftWorld();
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  await overview(page, repository.slug);
  await page.getByRole('button', { name: 'Publish…', exact: true }).click();
  await expect(dialog(page)).toBeVisible();

  const box = await dialog(page).boundingBox();

  expect(box).not.toBeNull();
  expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= 375).toBe(true);

  const heights = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('[data-publish-dialog] button')]
      .filter((element) => element.offsetParent !== null)
      .map((element) => Math.round(element.getBoundingClientRect().height)),
  );

  expect(heights.length).toBe(2);
  expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  await context.close();
});
