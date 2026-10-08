import { expect, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import { newLibrary, newRepository, newUser, publish, signedInPage } from './support';

// A repository with its owner, and another person who works on it as an Organizer.
async function studioWorld() {
  const owner = await newUser('owner', ['tenant_creator']);
  const organizer = await newUser('organizer');
  const repository = await newRepository(owner.api, `Bestiary ${crypto.randomUUID().slice(0, 8)}`);

  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: repository.id } },
      body: { user_id: organizer.me.id, role: 'orga' },
    }),
  );

  return { owner, organizer, repository };
}

function row(page: import('@playwright/test').Page, userId: string) {
  return page.locator('[data-members] > li').filter({ hasText: userId });
}

test('an account that may create makes a repository, which opens on its Overview', async ({
  browser,
}) => {
  const maker = await newUser('maker', ['tenant_creator']);
  const { page, context } = await signedInPage(browser, maker.subject);

  // Studio is in the header for someone who may make one, and opens on the form.
  await page.getByRole('banner').getByRole('link', { name: 'My repositories' }).click();
  await expect(page).toHaveURL(/\/studio\/\?new=1/);
  await expect(page.getByRole('heading', { name: 'Create a repository' })).toBeVisible();

  const name = `Core rules ${crypto.randomUUID().slice(0, 8)}`;

  await page.getByLabel('Repository name').fill(name);
  await page.getByRole('button', { name: 'Create repository' }).click();

  // It opens on its Overview: a draft, said in words.
  await expect(page).toHaveURL(/\/studio\/\?repository=/);
  await expect(page.getByRole('heading', { name })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Overview' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(page.locator('[data-overview] [data-state]')).toHaveText('Draft');
  await expect(
    page.getByText('Libraries it has been offered to cannot look inside it'),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: /^Publish/ })).toBeVisible();
  // A draft has nobody to be live for.
  await expect(page.locator('[data-live]')).toBeHidden();

  // It is in the list, and a repository made from the page is one, not a library.
  await expect(page.locator('[data-list]').getByRole('link', { name })).toBeVisible();
  const made = await ok(maker.api.GET('/tenants', { params: { query: { kind: 'repository' } } }));

  expect(made.items.map((t) => t.name)).toContain(name);
  await context.close();
});

test('an account that may not create, and works on nothing, is told so and offered nothing', async ({
  browser,
}) => {
  const plain = await newUser('plain');
  const { page, context } = await signedInPage(browser, plain.subject);

  await expect(page.getByRole('banner').getByRole('link', { name: 'My repositories' })).toHaveCount(
    0,
  );
  await page.goto('/studio/');
  await expect(page.getByText('You do not work on a repository yet.')).toBeVisible();
  await expect(
    page.getByText("Creating a repository isn't open to your account yet."),
  ).toBeVisible();
  await expect(page.getByLabel('Repository name')).toHaveCount(0);
  await context.close();
});

test('People: every role with what it means, and an Owner changes who works on it', async ({
  browser,
}) => {
  const { owner, organizer, repository } = await studioWorld();
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await page.getByRole('tab', { name: 'People' }).click();

  // The roles are explained next to the people who have them, in the glossary's words.
  const people = page.locator('[data-people]');

  await expect(people.getByRole('heading', { name: 'Who works on it' })).toBeVisible();
  await expect(people.locator('[data-roles] strong')).toHaveText(['Owner', 'Organizer']);
  await expect(people).toContainText('publishes the repository, invites libraries to it');
  await expect(people).toContainText(
    'Cannot publish it, invite libraries or change who works on it',
  );
  await expect(people).toContainText('an Organizer is the one who edits');
  await expect(people.getByRole('option', { name: 'Organizer' }).first()).toBeAttached();
  await expect(people).not.toContainText(/\borga\b/);

  // Both people are there, with their roles; an Owner has the controls.
  await expect(row(page, owner.me.id)).toBeVisible();
  await expect(row(page, organizer.me.id).getByRole('combobox')).toHaveValue('orga');

  await row(page, organizer.me.id).getByRole('combobox').selectOption('owner');
  await expect
    .poll(async () => {
      const roster = await ok(
        owner.api.GET('/tenants/{tenant_id}/memberships', {
          params: { path: { tenant_id: repository.id } },
        }),
      );

      const entry = roster.items.find(
        (m) => m.kind === 'membership' && m.user_id === organizer.me.id,
      );

      return entry?.kind === 'membership' ? entry.role : undefined;
    })
    .toBe('owner');

  await row(page, organizer.me.id).getByRole('button', { name: 'Remove' }).click();
  await expect(row(page, organizer.me.id)).toHaveCount(0);
  await context.close();
});

test('an Organizer reads who works on it and edits it, and changes nobody', async ({ browser }) => {
  const { owner, organizer, repository } = await studioWorld();
  const { page, context } = await signedInPage(browser, organizer.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(page.locator('[data-role]').first()).toHaveText('Organizer');
  // Whoever edits can rename it.
  await expect(page.getByRole('button', { name: 'Edit repository' })).toBeVisible();

  await page.getByRole('tab', { name: 'People' }).click();
  const list = page.locator('[data-people-list]');

  await expect(list).toBeVisible();
  await expect(list.locator('li')).toHaveCount(2);
  await expect(list.locator('li').filter({ hasText: owner.me.id })).toContainText('Owner');
  await expect(list.locator('li').filter({ hasText: organizer.me.id })).toContainText('Organizer');

  // Nothing to change it with.
  const panel = page.locator('[data-people]');

  await expect(panel.getByRole('button', { name: 'Remove' })).toHaveCount(0);
  await expect(panel.getByRole('combobox')).toHaveCount(0);
  await expect(panel.getByText('Add a person, as:')).toHaveCount(0);
  await context.close();
});

test('a published repository says so, and that libraries see edits live', async ({ browser }) => {
  const { owner, repository } = await studioWorld();

  await publish(owner.api, repository.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toHaveText(
    /^Published \d{4}-\d{2}-\d{2}$/,
  );
  await expect(page.locator('[data-live]')).toBeVisible();
  await expect(page.getByText('see your edits when they next check for updates')).toBeVisible();
  await context.close();
});

test('renaming and leaving, in the words of a repository', async ({ browser }) => {
  const { owner, organizer, repository } = await studioWorld();
  const { page, context, confirmations } = await signedInPage(browser, organizer.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);

  const renamed = `Renamed ${crypto.randomUUID().slice(0, 8)}`;

  await page.getByRole('button', { name: 'Edit repository' }).click();
  await page.getByLabel('Repository name').fill(renamed);
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('heading', { name: renamed })).toBeVisible();
  await expect(page.locator('[data-list]').getByRole('link', { name: renamed })).toBeVisible();

  const saved = await ok(
    owner.api.GET('/tenants/{tenant_id}', { params: { path: { tenant_id: repository.id } } }),
  );

  expect(saved.name).toBe(renamed);

  await page.getByRole('tab', { name: 'People' }).click();
  await page.getByRole('button', { name: 'Leave this repository' }).click();
  await expect(page.locator('[data-list]').getByRole('link', { name: renamed })).toHaveCount(0);
  expect(confirmations[0]).toContain(`Leave "${renamed}"?`);
  expect(confirmations[0].toLowerCase()).not.toContain('library');
  await context.close();
});

test('repositories are not on the libraries page: an address that names one goes to Studio', async ({
  browser,
}) => {
  const { owner, repository } = await studioWorld();
  const library = await newLibrary(owner.api, `Table ${crypto.randomUUID().slice(0, 8)}`);
  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto('/tenants/');
  await expect(
    page.locator('[data-libraries]').getByRole('link', { name: library.name }),
  ).toBeVisible();
  await expect(page.getByText(repository.name)).toHaveCount(0);

  await page.goto(`/tenants/?tenant=${repository.slug}`);
  await expect(page).toHaveURL(new RegExp(`/studio/\\?repository=${repository.slug}`));
  await expect(page.getByRole('heading', { name: repository.name })).toBeVisible();

  await page.goto('/tenants/?new=repository');
  await expect(page).toHaveURL(/\/studio\/\?new=1/);

  // The home page links to it there too.
  await page.goto('/');
  await expect(page.getByRole('link', { name: repository.name })).toHaveAttribute(
    'href',
    new RegExp(`/studio/\\?repository=${repository.slug}`),
  );
  await context.close();
});

test('on a phone, Studio is one column and everything pressed is big enough', async ({
  browser,
}) => {
  const { owner, repository } = await studioWorld();
  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  async function checkScreen() {
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );

    expect(overflow).toBeLessThanOrEqual(0);

    const heights = await page.evaluate(() =>
      [
        ...document.querySelectorAll<HTMLElement>(
          '[data-studio-panel] button, [data-studio-panel] .tab, [data-studio-panel] select, [data-studio-panel] .sidebar a',
        ),
      ]
        .filter((element) => element.offsetParent !== null)
        .map((element) => Math.round(element.getBoundingClientRect().height)),
    );

    expect(heights.length).toBeGreaterThan(0);
    expect(Math.min(...heights)).toBeGreaterThanOrEqual(44);
  }

  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(page.getByRole('heading', { name: repository.name })).toBeVisible();
  await checkScreen();

  await page.getByRole('tab', { name: 'People' }).click();
  await expect(page.locator('[data-members]')).toBeVisible();
  await checkScreen();
  await context.close();
});
