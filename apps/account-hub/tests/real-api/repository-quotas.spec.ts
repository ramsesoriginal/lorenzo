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
// REPOSITORY_MAX_ENTRIES). An Owner who adds entries by hand is stopped at the limit and told in the
// API's words; a repository that builds on another by copying it is not refused, however large the
// copy (ADR 0298), and what it brought counts when somebody adds by hand again.
test('adding past the limit by hand is refused in words; a copy past it is not', async ({
  browser,
}) => {
  const owner = await newUser('quota', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const source = await newRepository(owner.api, `Armoury ${tag}`);
  const bridge = await newRepository(owner.api, `Bridge ${tag}`);

  for (let i = 1; i <= 50; i++) await addItem(owner.api, bridge.id, `Own ${i}`);

  // By hand: the 51st entry is refused, and nothing is kept.
  const refused = await owner.api.POST('/tenants/{tenant_id}/items', {
    params: { path: { tenant_id: bridge.id } },
    body: { name: 'One too many', prototype_ids: [], in_public_catalog: false },
  });
  expect(refused.response.status).toBe(422);
  expect(refused.error).toMatchObject({
    type: 'repository-entry-limit',
    detail: 'This repository holds 50 entries, which is the most a repository can have.',
  });
  expect((await holdings(owner.api, bridge.id)).items).toBe(50);

  // The copy engine is exempt: the wizard copies 5 more entries into the full repository.
  for (let i = 1; i <= 5; i++) await addItem(owner.api, source.id, `Blade ${i}`);
  await publish(owner.api, source.id);
  await invite(owner.api, source.id, bridge.id);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/repositories/?tenant=${bridge.slug}&repository=${source.id}&copy=new`);
  await expect(page.getByRole('heading', { name: `Copy ${source.name}` })).toBeVisible();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Copy now' }).click();
  await expect(page.locator('[data-copy-step]')).toHaveText('Step 3 of 3: Done');
  expect((await holdings(owner.api, bridge.id)).items).toBe(55);

  // What it brought counts: one more by hand is still refused.
  const again = await owner.api.POST('/tenants/{tenant_id}/items', {
    params: { path: { tenant_id: bridge.id } },
    body: { name: 'Still too many', prototype_ids: [], in_public_catalog: false },
  });
  expect(again.response.status).toBe(422);
  await context.close();
});
