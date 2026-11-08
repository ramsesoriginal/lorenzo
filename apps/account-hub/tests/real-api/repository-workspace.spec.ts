import { expect, test } from '@playwright/test';
import { addItem, newRepository, newUser, signedInPage } from './support';

// A repository one works on is one click from the list of repositories, from Home and from the
// "still a draft" task, and its Owner finds there what they do with it: publish it, choose who sees it
// (public, protected or private) and choose what is shown of it. The list used to take such a click
// itself, and showed the page of what libraries use instead of the workspace.

test('the list of repositories opens a repository’s workspace, with publishing, visibility and Featured', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Workspace ${crypto.randomUUID().slice(0, 8)}`);

  await addItem(owner.api, repository.id, 'Owlbear');

  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 1440, height: 900 },
  });

  const reachesWorkspace = async () => {
    for (const tab of ['Overview', 'Profile', 'People', 'Releases', 'Activity']) {
      await expect(page.getByRole('tab', { name: tab }), tab).toBeVisible();
    }

    await expect(page.getByRole('button', { name: 'Publish…' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Make public…' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Make protected…' })).toBeVisible();
    // What is shown of it before it is copied, and which entries are featured.
    await expect(page.locator('[data-showcase]')).toBeVisible();
  };

  // From the list of repositories.
  await page.goto('/repositories/');
  await page.locator('[data-yours-list]').getByRole('link', { name: repository.name }).click();
  await expect(page).toHaveURL(/\/repositories\/\?repository=/);
  await reachesWorkspace();

  // From Home: the repository in "What you run", and the draft task.
  await page.goto('/');
  await page.locator('[data-run-list]').getByRole('link', { name: repository.name }).click();
  await expect(page).toHaveURL(/\/repositories\/\?repository=/);
  await reachesWorkspace();

  await page.goto('/');
  await page.locator('[data-needs-list]').getByRole('link', { name: 'Open it' }).click();
  await reachesWorkspace();

  // And a way back to the list through the place the header names.
  await page
    .getByRole('navigation', { name: 'Pages' })
    .getByRole('link', { name: 'Repositories' })
    .click();
  await expect(page.locator('[data-yours-list]')).toBeVisible();
  await context.close();
});
