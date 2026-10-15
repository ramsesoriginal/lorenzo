import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  API_URL,
  AUTHGEAR_URL,
  SITE_URL,
  SUBJECT_COOKIE,
} from '../../../inventory-web/tests/e2e/support/env';
import {
  addItem,
  invite,
  newLibrary,
  newRepository,
  newUser,
  publish,
  signedInPage,
} from './support';

// ADR 0300: a private repository's picture is for a signed-in user, and an <img src> cannot send
// the token, so every place that shows one fetches it with the token. Each test collects what the
// page asked of `/tenants/{id}/picture` and holds it to carrying one.

// A one-pixel PNG.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

async function withPicture(api: Awaited<ReturnType<typeof newUser>>['api'], tenantId: string) {
  await ok(
    api.PUT('/tenants/{tenant_id}/picture', {
      params: { path: { tenant_id: tenantId } },
      body: { file: 'picture.png' },
      bodySerializer: () => {
        const data = new FormData();

        data.append('file', new Blob([PNG], { type: 'image/png' }), 'picture.png');

        return data;
      },
    }),
  );
}

// The requests a page makes of a tenant's picture, with whether each one sent a token.
function watchPicture(page: Page, tenantId: string) {
  const asked: { url: string; token: boolean }[] = [];

  page.on('request', (request) => {
    if (request.url().includes(`/tenants/${tenantId}/picture`)) {
      asked.push({ url: request.url(), token: Boolean(request.headers().authorization) });
    }
  });

  return asked;
}

test('a repository on the shelf shows its picture, asked for with the token', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api, `Table ${crypto.randomUUID()}`);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Armoury ${tag}`);

  await addItem(owner.api, repository.id, 'Longsword');
  await publish(owner.api, repository.id);
  await invite(owner.api, repository.id, library.id);
  await withPicture(owner.api, repository.id);

  const { page, context } = await signedInPage(browser, owner.subject);
  const asked = watchPicture(page, repository.id);

  await page.goto(`/repositories/?tenant=${library.slug}`);

  const card = page.getByRole('listitem').filter({ hasText: `Armoury ${tag}` });

  await expect(card.locator('[data-picture]')).toBeVisible();
  await expect(card.locator('[data-initial]')).toBeHidden();
  expect(await card.locator('[data-picture]').getAttribute('src')).toMatch(/^blob:/);
  expect(asked.length).toBeGreaterThan(0);
  expect(asked.every((request) => request.token)).toBe(true);

  // The same picture on the repository's own page.
  await card.getByRole('link', { name: `Armoury ${tag}` }).click();
  await expect(page.getByRole('heading', { name: `Armoury ${tag}` })).toBeVisible();
  await expect(page.locator('[data-picture]:visible').first()).toBeVisible();
  expect(asked.every((request) => request.token)).toBe(true);

  await context.close();
});

test('a repository editor shows the picture and takes a new one, each fetched with the token', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Bestiary ${crypto.randomUUID().slice(0, 8)}`);

  await withPicture(owner.api, repository.id);

  const { page, context } = await signedInPage(browser, owner.subject);
  const asked = watchPicture(page, repository.id);

  await page.goto(`/studio/?repository=${repository.id}`);
  await expect(page.getByRole('heading', { name: repository.name })).toBeVisible();

  const picture = page.locator('[data-picture-slot] [data-picture]');

  await expect(picture).toHaveAttribute('src', /^blob:/);
  const first = await picture.getAttribute('src');

  await page.locator('[data-picture-slot] [data-file]').setInputFiles({
    name: 'new.png',
    mimeType: 'image/png',
    buffer: PNG,
  });
  await expect(page.locator('[data-picture-slot] [data-status]')).toHaveText('Updated.');
  // Asked for afresh: a new blob, not the one it already had.
  await expect.poll(async () => picture.getAttribute('src')).not.toBe(first);
  await expect(picture).toHaveAttribute('src', /^blob:/);
  expect(asked.length).toBeGreaterThanOrEqual(2);
  expect(asked.every((request) => request.token)).toBe(true);

  await context.close();
});

test('the API gives nothing of a private repository to a request with no token', async ({
  request,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Hidden ${crypto.randomUUID().slice(0, 8)}`);

  await withPicture(owner.api, repository.id);

  const closed = await request.get(`${API_URL}/tenants/${repository.id}/picture`);
  const unknown = await request.get(`${API_URL}/tenants/${crypto.randomUUID()}/picture`);

  expect(closed.status()).toBe(404);
  expect(unknown.status()).toBe(404);
  expect(await closed.body()).not.toEqual(PNG);
});

test('an invite link to a private repository shows its picture only to someone logged in', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const repository = await newRepository(owner.api, `Shared ${crypto.randomUUID().slice(0, 8)}`);

  await withPicture(owner.api, repository.id);

  const created = await ok(
    owner.api.POST('/tenants/{tenant_id}/invites', {
      params: { path: { tenant_id: repository.id } },
      body: { kind: 'library_access' },
    }),
  );
  const guest = await newUser('guest');
  const context = await browser.newContext();
  const page = await context.newPage();
  const asked = watchPicture(page, repository.id);

  await context.addCookies([{ name: SUBJECT_COOKIE, value: guest.subject, url: AUTHGEAR_URL }]);
  await page.goto(`/join/#${created.token}`);
  await expect(page.locator('[data-campaign]')).toHaveText(repository.name);
  // Not logged in: the page asks as it is, and a private repository answers no picture.
  await expect(page.locator('[data-picture]')).toBeHidden();

  await page.getByRole('button', { name: 'Log in to join' }).click();
  await expect(page).toHaveURL(`${SITE_URL}/join/`);
  // Logged in: asked for with the token, and shown.
  await expect(page.locator('[data-picture]')).toBeVisible();
  expect(await page.locator('[data-picture]').getAttribute('src')).toMatch(/^blob:/);
  expect(asked.some((request) => request.token)).toBe(true);

  await context.close();
});
