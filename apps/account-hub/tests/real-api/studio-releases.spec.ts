import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import { addItem, invite, newLibrary, newRepository, newUser, signedInPage } from './support';

async function release(api: Api, repositoryId: string, label?: string, acknowledge = false) {
  return ok(
    api.PUT('/tenants/{tenant_id}/published', {
      params: { path: { tenant_id: repositoryId } },
      body: { ...(label ? { label } : {}), breaking: false, acknowledge_breaking: acknowledge },
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

async function rename(api: Api, tenantId: string, entityId: string, name: string) {
  await ok(
    api.PATCH('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { name },
    }),
  );
}

// A repository with a library invited to it, two items, and nothing published yet.
async function releaseWorld() {
  const owner = await newUser('owner', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);
  const library = await newLibrary(owner.api, `Table ${tag}`);
  const owlbear = await addItem(owner.api, repository.id, 'Owlbear', 'owlbear');
  const troll = await addItem(owner.api, repository.id, 'Troll');

  await invite(owner.api, repository.id, library.id);

  return { owner, repository, library, owlbear, troll, tag };
}

const dialog = (page: Page) => page.locator('[data-publish-dialog]');

async function overview(page: Page, slug: string) {
  await page.goto(`/studio/?repository=${slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
}

test('the composer: a label and notes for the first release, and what it will contain', async ({
  browser,
}) => {
  const { owner, repository } = await releaseWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(page.locator('[data-matches]')).toHaveText(/No release yet/);
  await page.getByRole('button', { name: 'Publish…', exact: true }).click();

  // What it will contain, from the API's preview; nothing is made to read it.
  await expect(dialog(page).getByLabel('Label')).toBeVisible();
  await expect(dialog(page)).toContainText('Left empty, it is 1.');
  await expect(dialog(page)).toContainText('Entries: 2 added.');
  await expect(dialog(page)).toContainText('New: “Owlbear”, “Troll”.');
  await expect(dialog(page)).toContainText('Text edits are not tracked');
  await expect(dialog(page)).toContainText('No release yet');
  expect(await dialog(page).innerText()).not.toMatch(/stable|frozen/i);

  await dialog(page).getByLabel('Label').fill('1.0');
  await dialog(page).getByLabel('Notes', { exact: true }).fill('The first monsters.');
  await dialog(page).getByRole('button', { name: 'Publish and tell 1 library' }).click();
  await expect(page.locator('[data-publish-status]')).toHaveText('Release published.');

  // The Overview says what it matches, and the tab lists it with what it said.
  await expect(page.locator('[data-matches]')).toHaveText('Matches release 1.0.');
  await expect(page.locator('[data-text-not-tracked]')).toContainText('Text edits are not tracked');
  await page.getByRole('tab', { name: 'Releases' }).click();

  const first = page.locator('[data-releases-list] > li').first();

  await expect(first).toContainText('1.0');
  await expect(first).toContainText('The first monsters.');
  await expect(first).toContainText('Release 1');
  await expect(first).toContainText('Entries: 2 added.');
  await expect(first.locator('[data-breaking]')).toBeHidden();
  await context.close();
});

test('edits since a release are said as such, and a new release says what changed', async ({
  browser,
}) => {
  const { owner, repository, troll } = await releaseWorld();

  await release(owner.api, repository.id, '1.0');
  await rename(owner.api, repository.id, troll.entity_id, 'Cave troll');

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await expect(page.locator('[data-matches]')).toHaveText(
    'Edited since release 1.0: 1 row differs.',
  );

  await page.getByRole('button', { name: 'Publish a new release…' }).click();
  await expect(dialog(page)).toContainText('Edited since release 1.0: 1 row differs.');
  await expect(dialog(page)).toContainText('Entries: 1 changed.');
  await expect(dialog(page).getByLabel('Label')).toHaveValue('');
  await expect(dialog(page)).toContainText('Left empty, it is 2.');
  await dialog(page).getByLabel('Label').fill('Errata');
  await dialog(page).getByRole('button', { name: 'Publish release and tell 1 library' }).click();
  await expect(page.locator('[data-matches]')).toHaveText('Matches release Errata.');
  await context.close();
});

test('a release that breaks things lists them and is published only once they are acknowledged', async ({
  browser,
}) => {
  const { owner, repository, troll } = await releaseWorld();

  await release(owner.api, repository.id, '1.0');
  // The troll is dropped: a library that copied it can only keep it.
  await ok(
    owner.api.DELETE('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { tenant_id: repository.id, entity_id: troll.entity_id } },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await page.getByRole('button', { name: 'Publish a new release…' }).click();
  await expect(dialog(page)).toContainText('This release breaks things');
  await expect(dialog(page)).toContainText('“Troll” was removed.');
  await expect(dialog(page)).toContainText('Removed: “Troll”.');

  // Not until it is acknowledged, and the refusal says why.
  await dialog(page).getByRole('button', { name: 'Publish release and tell 1 library' }).click();
  await expect(dialog(page).locator('[data-dialog-error]')).toContainText(
    'This release breaks things',
  );
  await expect(page.locator('[data-publish-status]')).not.toHaveText('Release published.');

  await dialog(page)
    .getByLabel(/I understand that these changes break libraries/)
    .check();
  await dialog(page).getByLabel('Label').fill('2.0');
  await dialog(page).getByRole('button', { name: 'Publish release and tell 1 library' }).click();
  await expect(page.locator('[data-publish-status]')).toHaveText('Release published.');

  // The release is marked breaking and keeps what it broke.
  await page.getByRole('tab', { name: 'Releases' }).click();

  const latest = page.locator('[data-releases-list] > li').first();

  await expect(latest).toContainText('2.0');
  await expect(latest.locator('[data-breaking]')).toBeVisible();
  await latest.getByText('What it breaks (1)').click();
  await expect(latest).toContainText('“Troll” was removed.');
  await context.close();
});

test('a label that is taken is refused in the API’s words, whatever its case', async ({
  browser,
}) => {
  const { owner, repository } = await releaseWorld();

  await release(owner.api, repository.id, 'Spring');

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await page.getByRole('button', { name: 'Publish a new release…' }).click();
  await dialog(page).getByLabel('Label').fill('spring');
  await dialog(page).getByRole('button', { name: 'Publish release and tell 1 library' }).click();
  await expect(dialog(page).locator('[data-dialog-error]')).toContainText('is already called');
  await expect(dialog(page)).toBeVisible();
  await context.close();
});

test('an Owner changes a release’s label and notes, and nothing else of it', async ({
  browser,
}) => {
  const { owner, repository } = await releaseWorld();

  await release(owner.api, repository.id, '1.0');

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await page.getByRole('tab', { name: 'Releases' }).click();

  const first = page.locator('[data-releases-list] > li').first();

  await first.getByRole('button', { name: 'Edit label and notes' }).click();
  await first.getByLabel('Label').fill('1.0 final');
  await first.getByLabel('Notes', { exact: true }).fill('Corrected notes.');
  await first.getByRole('button', { name: 'Save' }).click();
  await expect(page.locator('[data-releases-list] > li').first()).toContainText('1.0 final');
  await expect(page.locator('[data-releases-list] > li').first()).toContainText('Corrected notes.');
  await expect(page.locator('[data-matches]')).toHaveText('Matches release 1.0 final.');
  await context.close();
});

test('who is on which release: the owner sees it per library, and a library sees it on the repository', async ({
  browser,
}) => {
  const { owner, repository, library, owlbear } = await releaseWorld();

  await release(owner.api, repository.id, '1.0');
  await copyInto(owner.api, library.id, repository.id);
  await rename(owner.api, repository.id, owlbear.entity_id, 'Owlbear +1');
  await release(owner.api, repository.id, '1.1');

  const { page, context } = await signedInPage(browser, owner.subject);

  await overview(page, repository.slug);
  await page.getByRole('tab', { name: 'Libraries using it' }).click();
  await expect(
    page.locator('[data-using-list] > li').filter({ hasText: library.name }),
  ).toContainText('on release 1.0');

  // The library's own page for it says which release it took, and which is the latest.
  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}`);
  await expect(page.locator('[data-history]')).toContainText('Last updated from release');
  await expect(page.locator('[data-history]')).toContainText('1.0');
  await expect(page.locator('[data-history]')).toContainText('Latest release');
  await expect(page.locator('[data-history]')).toContainText('1.1');
  await context.close();
});

test('the update inbox marks rows against the release, and apply all clean takes only what is released', async ({
  browser,
}) => {
  const { owner, repository, library, owlbear, troll } = await releaseWorld();

  await release(owner.api, repository.id, '1.0');
  await copyInto(owner.api, library.id, repository.id);

  // The owlbear is renamed and released; the troll is renamed after the release.
  await rename(owner.api, repository.id, owlbear.entity_id, 'Owlbear +1');
  await release(owner.api, repository.id, '1.1');
  await rename(owner.api, repository.id, troll.entity_id, 'Cave troll');

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}&updates=1`);
  await expect(page.getByRole('heading', { name: 'Changed (2)' })).toBeVisible();
  await expect(page.locator('[data-updates-notes]')).toContainText('Latest release: 1.1.');

  const released = page.locator('[data-groups] li').filter({ hasText: 'Owlbear' }).first();
  const edited = page.locator('[data-groups] li').filter({ hasText: 'Troll' }).first();

  await expect(released).toContainText('In release 1.1');
  await expect(edited).toContainText('Edited since release 1.1');

  // Apply all clean takes the released row, and leaves the edited one for its own decision.
  await expect(page.locator('[data-bulk-sentence]')).toHaveText(
    'Apply 1 change. Left for you to decide: 1 edited since the release.',
  );
  await page.getByRole('button', { name: 'Apply all clean' }).click();
  await page.getByRole('button', { name: 'Apply now' }).click();
  await expect(page.locator('[data-result-text]')).toHaveText('Applied 1 change.');

  const items = await ok(
    owner.api.GET('/tenants/{tenant_id}/items', { params: { path: { tenant_id: library.id } } }),
  );
  const names = items.items.map((item) => item.title);

  expect(names).toContain('Owlbear +1');
  expect(names).toContain('Troll');
  await context.close();
});

test('a row a release called breaking is applied only after its notes are confirmed', async ({
  browser,
}) => {
  const { owner, repository, library, owlbear } = await releaseWorld();

  await release(owner.api, repository.id, '1.0');
  await copyInto(owner.api, library.id, repository.id);
  // Its link name changes, which a release must acknowledge, since links in copied text keep the old one.
  await ok(
    owner.api.PUT('/tenants/{tenant_id}/entities/{entity_id}/slug', {
      params: { path: { tenant_id: repository.id, entity_id: owlbear.entity_id } },
      body: { slug: 'owl-bear' },
    }),
  );
  await release(owner.api, repository.id, '2.0', true);

  const { page, context, confirmations } = await signedInPage(browser, owner.subject);

  await page.goto(`/repositories/?tenant=${library.slug}&repository=${repository.id}&updates=1`);

  const row = page.locator('[data-groups] li').filter({ hasText: 'Owlbear' }).first();

  await expect(row).toContainText('Breaking in release 2.0');
  // There is nothing clean to apply all at once: it is left for its own decision.
  await expect(page.getByRole('button', { name: 'Apply all clean' })).toBeHidden();

  await row.getByRole('button', { name: 'Apply' }).click();
  await expect(page.locator('[data-result-text]')).toHaveText('Applied 1 change.');
  expect(confirmations[0]).toContain('Breaking in release 2.0');
  expect(confirmations[0]).toContain('Apply it anyway?');

  const entry = await ok(
    owner.api.GET('/tenants/{tenant_id}/entities/by-slug/{slug}', {
      params: { path: { tenant_id: library.id, slug: 'owl-bear' } },
    }),
  );

  expect(entry.name).toBe('Owlbear');
  await context.close();
});

test('on a phone, the composer fits and everything pressed is big enough', async ({ browser }) => {
  const { owner, repository } = await releaseWorld();
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  await overview(page, repository.slug);
  await page.getByRole('button', { name: 'Publish…', exact: true }).click();
  await expect(dialog(page).getByLabel('Label')).toBeVisible();

  const box = await dialog(page).boundingBox();

  expect(box).not.toBeNull();
  expect((box?.x ?? -1) >= 0 && (box?.x ?? 0) + (box?.width ?? 0) <= 375).toBe(true);

  const heights = await page.evaluate(() =>
    [
      ...document.querySelectorAll<HTMLElement>(
        '[data-publish-dialog] button, [data-publish-dialog] .text-input, [data-publish-dialog] .field-row',
      ),
    ]
      .filter((element) => element.offsetParent !== null)
      .map((element) => Math.round(element.getBoundingClientRect().height)),
  );

  expect(heights.length).toBeGreaterThan(3);
  expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  await context.close();
});
