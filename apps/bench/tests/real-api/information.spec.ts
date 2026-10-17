import { randomUUID } from 'node:crypto';
import { ok } from '../../../beings/tests/e2e/support/api.ts';
import { expect, test } from '../../../beings/tests/e2e/support/fixtures.ts';

test('a fact keeps separate audiences, explicit subjects and targeted picture bundles', async ({
  world,
  as,
}) => {
  test.slow();
  const api = world.gm.api;
  const repository = await ok(
    api.POST('/tenants', { body: { name: `Facts ${randomUUID()}`, kind: 'repository' } }),
  );
  const path = { tenant_id: repository.id };
  const lich = await ok(
    api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'A lich', kinds: ['being'], parents: [] },
    }),
  );
  const weapon = await ok(
    api.POST('/tenants/{tenant_id}/entities', {
      params: { path },
      body: { name: 'A weapon', kinds: ['item'], parents: [] },
    }),
  );
  const page = await as(world.gm);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.locator('#titlebar')).toContainText(repository.name);
  await page.getByRole('button', { name: 'New', exact: true }).click();
  const form = page.locator('.new-entry');
  await form.getByLabel('Name of the new entry').fill('The tether');
  await form.getByLabel('Kind of the new entry').selectOption('fact');
  await form.getByLabel('Parent of the new entry').selectOption('');
  await form.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('The tether');
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');
  const facts = await ok(
    api.GET('/tenants/{tenant_id}/entities/resolve', {
      params: { path, query: { slug: ['the-tether'] } },
    }),
  );
  const fact = facts[0];
  if (!fact) throw new Error('The new fact was not found.');
  expect(fact.kinds).toEqual(['fact']);
  const entry = { ...path, entity_id: fact.entity_id };
  const detail = () =>
    ok(api.GET('/tenants/{tenant_id}/entities/{entity_id}', { params: { path: entry } }));
  const png = await page.screenshot();
  const body = page.locator('.information-body').first();
  const source = page.getByLabel('Description', { exact: true });
  await source.fill('The weapon holds the lich’s soul.');
  let lost = false;
  await page.route('**/information/*/payloads', async (route) => {
    if (route.request().method() === 'POST' && !lost) {
      lost = true;
      expect((await route.fetch()).status()).toBe(201);
      await route.abort('failed');
    } else await route.continue();
  });
  await body
    .locator('input[type=file]')
    .setInputFiles({ name: 'map.png', mimeType: 'image/png', buffer: png });
  await expect(page.getByRole('button', { name: 'Retry picture', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Retry picture', exact: true }).click();
  await expect(body.locator('img')).toHaveCount(1);
  await expect(source).toBeFocused();
  const bytes = Array.from(png);
  const data = await page.evaluateHandle((bytes) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File([new Uint8Array(bytes)], 'map.png', { type: 'image/png' }));
    return transfer;
  }, bytes);
  await source.evaluate(
    (element, transfer) =>
      element.dispatchEvent(
        new ClipboardEvent('paste', { clipboardData: transfer, bubbles: true, cancelable: true }),
      ),
    data,
  );
  await expect(body.locator('img')).toHaveCount(2);
  await body.evaluate(
    (element, transfer) =>
      element.dispatchEvent(
        new DragEvent('drop', { dataTransfer: transfer, bubbles: true, cancelable: true }),
      ),
    data,
  );
  await expect(body.locator('img')).toHaveCount(3);
  const description = (await detail()).information.find((info) => info.type === 'description');
  expect(description?.payloads.map((p) => p.kind)).toEqual([
    'description',
    'picture',
    'picture',
    'picture',
  ]);
  expect(description?.payloads[0]).toMatchObject({ content: 'The weapon holds the lich’s soul.' });
  await page.getByText('Who knows this exists', { exact: true }).click();
  const outer = page
    .locator('.entry-audience')
    .filter({ has: page.getByText('Who knows this exists', { exact: true }) });
  await outer.getByLabel('Everyone with access to the library', { exact: true }).check();
  await outer.getByRole('button', { name: 'Save audience' }).click();
  await expect
    .poll(
      async () =>
        (
          await ok(
            api.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
              params: { path: entry },
            }),
          )
        ).is_public,
    )
    .toBe(true);
  expect((await detail()).information[0]?.is_public).toBe(false);
  await page.getByText('Who can read this', { exact: true }).click();
  const inner = page
    .locator('.entry-audience')
    .filter({ has: page.getByText('Who can read this', { exact: true }) });
  await inner.getByLabel('Everyone with access to the library', { exact: true }).check();
  await inner.getByRole('button', { name: 'Save audience' }).click();
  await expect.poll(async () => (await detail()).information[0]?.is_public).toBe(true);
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');
  for (const subject of [lich, weapon]) {
    await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');
    await page.getByText('About', { exact: true }).click();
    await expect(page.getByLabel('What is this fact about?')).toBeVisible();
    await page.getByLabel('What is this fact about?').selectOption(subject.id);
    await page.getByRole('button', { name: 'Add subject', exact: true }).click();
    await expect
      .poll(async () =>
        (
          await ok(
            api.GET('/tenants/{tenant_id}/entities/{entity_id}/about', { params: { path: entry } }),
          )
        ).some((row) => row.id === subject.id),
      )
      .toBe(true);
  }
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');
  await body.locator('.picture-part-actions summary').first().click();
  await body.getByRole('button', { name: 'Move picture up', exact: true }).first().click();
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');
  expect(
    (await detail()).information
      .find((info) => info.type === 'description')
      ?.payloads.map((p) => p.kind),
  ).toEqual(['picture', 'description', 'picture', 'picture']);
  await page.locator('.pane-entry').getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(page.locator('.pane-entry .status-synced')).toHaveText('Synced');
  expect(
    (await detail()).information
      .find((info) => info.type === 'description')
      ?.payloads.map((p) => p.kind),
  ).toEqual(['description', 'picture', 'picture', 'picture']);
  await body.locator('.picture-part-actions summary').last().click();
  page.once('dialog', (dialog) => void dialog.accept());
  await body.getByRole('button', { name: 'Remove picture', exact: true }).last().click();
  await expect(body.locator('img')).toHaveCount(2);
  const note = page.locator('.new-note');
  await note.getByLabel('A new note', { exact: true }).fill('The GM’s annotated sketch.');
  await note
    .locator('input[type=file]')
    .setInputFiles({ name: 'gm-map.png', mimeType: 'image/png', buffer: png });
  await expect(page.locator('.note-row img')).toHaveCount(1);
  await page.getByLabel('Name', { exact: true }).fill('The lich’s tether');
  await page.getByLabel('Name', { exact: true }).press('Tab');
  await expect.poll(async () => (await detail()).name).toBe('The lich’s tether');
  await page.screenshot({ path: 'test-results/bench-information.png', fullPage: true });
  await page.reload();
  await page.getByRole('button', { name: 'A to Z', exact: true }).click();
  await page.locator(`[data-entry="${fact.entity_id}"]`).first().click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('The lich’s tether');
  await expect(page.locator('.information-body').first().locator('img')).toHaveCount(2);
  await expect(page.locator('.note-row img')).toHaveCount(1);
  const final = await detail();
  expect(final.information.find((info) => info.type === 'note')?.is_public).toBe(false);
});
