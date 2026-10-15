import { expect, test } from '@playwright/test';
import {
  addItem,
  holdings,
  invite,
  newRepository,
  newUser,
  publish,
  signedInPage,
} from './support';

// The API for these specs runs with a repository holding at most 50 entries (playwright config,
// REPOSITORY_MAX_ENTRIES): a repository that builds on another, by copying it, is refused when the
// copy would take it past that, and the copy wizard says so in the API's words.
test('a repository that would hold too many entries cannot copy another, and says so', async ({
  browser,
}) => {
  const owner = await newUser('quota', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const source = await newRepository(owner.api, `Armoury ${tag}`);
  const bridge = await newRepository(owner.api, `Bridge ${tag}`);

  for (let i = 1; i <= 31; i++) await addItem(owner.api, source.id, `Blade ${i}`);
  for (let i = 1; i <= 30; i++) await addItem(owner.api, bridge.id, `Own ${i}`);
  await publish(owner.api, source.id);
  await invite(owner.api, source.id, bridge.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/repositories/?tenant=${bridge.slug}&repository=${source.id}&copy=new`);
  await expect(page.getByRole('heading', { name: `Copy ${source.name}` })).toBeVisible();
  await page.getByRole('button', { name: 'Continue' }).click();

  await expect(page.locator('[data-copy-error]')).toHaveText(
    'This would make 61 entries in this repository, and a repository can have 50 at most. It holds 30. Nothing was copied.',
  );
  // Nothing was written: the bridge holds what it did.
  expect((await holdings(owner.api, bridge.id)).items).toBe(30);
  await context.close();
});
