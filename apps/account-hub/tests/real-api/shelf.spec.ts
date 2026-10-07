import { expect, test } from '@playwright/test';
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

// A small world, all through the API: a core repository, a repository built on it (so the
// library is invited to the one and not the other), and a draft nobody has published.
async function shelfWorld() {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api, `Table ${crypto.randomUUID()}`);
  // Names are made with a tag: a repository's slug is unique, and the tests share a database.
  const tag = crypto.randomUUID().slice(0, 8);
  const core = await newRepository(owner.api, `Core rules ${tag}`);
  const bridge = await newRepository(owner.api, `Faerûn campaign ${tag}`);
  const draft = await newRepository(owner.api, `Unfinished setting ${tag}`);

  await addItem(owner.api, core.id, 'Longsword');
  await publish(owner.api, core.id);
  await invite(owner.api, core.id, bridge.id);
  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: bridge.id, repository_id: core.id } },
      body: {},
    }),
  );

  await addItem(owner.api, bridge.id, 'Flaming Longsword');
  await ok(
    owner.api.POST('/tenants/{tenant_id}/stat-groups', {
      params: { path: { tenant_id: bridge.id } },
      body: { name: 'Fire', priority: 0, mandatory: false },
    }),
  );
  await publish(owner.api, bridge.id);

  // The library is invited to the bridge and the draft, and not to the core it is built on.
  await invite(owner.api, bridge.id, library.id);
  await invite(owner.api, draft.id, library.id);

  return { owner, library, core, bridge, draft };
}

test('a library admin sees what is offered, what a repository holds and what it is built on', async ({
  browser,
}) => {
  const { owner, library } = await shelfWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  // The header offers Shelf to someone who runs a library.
  await expect(page.getByRole('banner').getByRole('link', { name: 'Repositories' })).toBeVisible();
  await page.goto(`/repositories/?tenant=${library.slug}`);

  // The list: each repository with its state in words.
  const bridgeCard = page.getByRole('listitem').filter({ hasText: 'Faerûn campaign' });
  await expect(bridgeCard).toContainText('Not copied yet');
  await expect(page.getByRole('listitem').filter({ hasText: 'Unfinished setting' })).toContainText(
    'Not published',
  );
  // The core is not on offer to this library, so it is not here.
  await expect(page.getByRole('link', { name: 'Core rules' })).toHaveCount(0);

  // A repository's page, by a plain click that keeps the address true.
  await bridgeCard.getByRole('link', { name: 'Faerûn campaign' }).click();
  await expect(page).toHaveURL(/repository=/);
  await expect(page.getByRole('heading', { name: 'Faerûn campaign' })).toBeVisible();
  await expect(page.getByText('has not copied it yet')).toBeVisible();

  // The API counts nothing while a repository it is built on is not offered to the library, so the
  // page says that and does not show a row of zeros.
  await expect(
    page.getByText('counted once every repository this one is built on is offered'),
  ).toBeVisible();
  await expect(page.locator('[data-inside]')).toBeEmpty();
  await expect(page.getByText('Only names show until your library copies')).toBeVisible();

  // Built on: this repository, and the core it needs and the library cannot yet take in.
  const outline = page.getByRole('list', { name: 'Built on' });
  await expect(outline).toContainText('Faerûn campaign');
  await expect(outline).toContainText('This repository');
  await expect(outline).toContainText('Core rules');
  await expect(outline).toContainText('Not invited');
  await expect(outline).toContainText(/Ask the owner of Core rules \S+ to invite your library\./);

  // Entries and stat groups are read when their sections are opened.
  await page.getByText('Entries', { exact: true }).click();
  const entry = page.locator('[data-entries] > li').filter({ hasText: 'Flaming Longsword' });
  await expect(entry).toBeVisible();
  await expect(entry).toContainText('Item');
  await page.getByLabel('Find an entry').fill('zzzz');
  await expect(page.getByText('No entry matches.')).toBeVisible();
  await page.getByText('Stat groups', { exact: true }).click();
  await expect(page.locator('[data-stat-groups]')).toContainText('Fire');

  // And back to the list.
  await page.getByRole('link', { name: 'All repositories' }).click();
  await expect(page).not.toHaveURL(/repository=/);
  await expect(bridgeCard).toBeVisible();
  await context.close();
});

test('a library that copied a repository, and one that lost its invitation, say so', async ({
  browser,
}) => {
  const { owner, library, core } = await shelfWorld();
  const second = await newLibrary(owner.api, `Second ${crypto.randomUUID()}`);

  await invite(owner.api, core.id, second.id);
  await ok(
    owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
      params: { path: { tenant_id: second.id, repository_id: core.id } },
      body: {},
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject);
  await page.goto(`/repositories/?tenant=${library.slug}`);

  // Someone who runs two libraries chooses one; the address follows.
  await page.getByLabel('Library').selectOption({ label: second.name });
  await expect(page).toHaveURL(new RegExp(`tenant=${second.slug}`));
  await expect(page.getByRole('listitem').filter({ hasText: 'Core rules' })).toContainText(
    'Copied',
  );

  // The invitation is withdrawn: what was copied stays, and the page says so.
  await ok(
    owner.api.DELETE('/tenants/{tenant_id}/subscribers/{subscriber_tenant_id}', {
      params: { path: { tenant_id: core.id, subscriber_tenant_id: second.id } },
    }),
  );
  await page.reload();
  const card = page.getByRole('listitem').filter({ hasText: 'Core rules' });
  await expect(card).toContainText('No longer offered');
  await card.getByRole('link', { name: 'Core rules' }).click();
  await expect(page.getByText('What you copied stays yours')).toBeVisible();
  await context.close();
});

test('a repository that is built on nothing shows what is inside it', async ({ browser }) => {
  const { owner, core } = await shelfWorld();
  const library = await newLibrary(owner.api, `Counts ${crypto.randomUUID()}`);

  await invite(owner.api, core.id, library.id);

  const { page, context } = await signedInPage(browser, owner.subject);
  await page.goto(`/repositories/?tenant=${library.slug}&repository=${core.id}`);

  await expect(page.locator('[data-inside]')).toContainText(/Entries\s*1(?!\d)/);
  await expect(page.getByRole('list', { name: 'Built on' })).toContainText('This repository');
  await expect(page.getByText('It is not built on other repositories.')).toBeVisible();
  await context.close();
});

test('someone who runs no library is told what repositories are for', async ({ browser }) => {
  const nobody = await newUser('nobody');
  const { page, context } = await signedInPage(browser, nobody.subject);

  await page.goto('/repositories/');
  await expect(page.getByText('you do not run one yet')).toBeVisible();
  await context.close();
});

test('on a phone the page is one column and what is pressed is big enough', async ({ browser }) => {
  const { owner, library, bridge } = await shelfWorld();
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  for (const path of [
    `/repositories/?tenant=${library.slug}`,
    `/repositories/?tenant=${library.slug}&repository=${bridge.id}`,
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole('heading', { name: /Repositories|Faerûn campaign/ }).first(),
    ).toBeVisible();
    await expect(page.locator('[data-repositories-panel]')).toBeVisible();

    // Nothing runs past the screen.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  }

  // On the repository's page, every node of the outline and every control is at least 44px tall.
  const heights = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('.outline-node, summary, [data-back]')]
      .filter((element) => element.offsetParent !== null)
      .map((element) => Math.round(element.getBoundingClientRect().height)),
  );

  expect(heights.length).toBeGreaterThan(0);
  expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  await context.close();
});
