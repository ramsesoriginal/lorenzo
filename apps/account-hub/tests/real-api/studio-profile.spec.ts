import { expect, type Page, test } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import { colourPng } from './png';
import { addItem, invite, newRepository, newUser, publish, signedInPage } from './support';

// ADR 0385: Studio's Profile tab and the cover controls, and the readiness list beside the visibility
// card. The launcher sets PUBLIC_REPOSITORIES_ENABLED for this suite (playwright.real-api.config.ts).
// Every test works in words of its own (a tag in each name), since Discover lists the whole
// deployment's repositories and the tests share it.

type Person = Awaited<ReturnType<typeof newUser>>;

const BLUE = colourPng(60, 20, [30, 60, 200]);
const GREEN = colourPng(60, 20, [30, 160, 60]);

const profilePanel = (page: Page) => page.locator('[data-profile]');
const summary = (page: Page) => page.locator('#profile-summary');
const saveButton = (page: Page) =>
  profilePanel(page).getByRole('button', { name: 'Save', exact: true });
const revertButton = (page: Page) =>
  profilePanel(page).getByRole('button', { name: 'Revert', exact: true });
const status = (page: Page) => page.locator('[data-profile-status]');
const cover = (page: Page) => page.locator('[data-cover-card]');
const problem = (page: Page, key: string) =>
  page.locator(`[data-profile-form] [data-problem="${key}"]`);
const creditRow = (page: Page, index: number) => page.locator('[data-credit]').nth(index);

async function openProfile(page: Page, slug: string) {
  await page.goto(`/studio/?repository=${slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
  await page.getByRole('tab', { name: 'Profile' }).click();
  await expect(profilePanel(page)).toBeVisible();
}

async function profileOf(api: Api, repositoryId: string) {
  return ok(
    api.GET('/tenants/{tenant_id}/profile', { params: { path: { tenant_id: repositoryId } } }),
  );
}

async function setCover(api: Api, repositoryId: string, png: Buffer) {
  await ok(
    api.PUT('/tenants/{tenant_id}/profile/cover', {
      params: { path: { tenant_id: repositoryId } },
      body: { file: 'cover.png' },
      bodySerializer: () => {
        const data = new FormData();

        data.append('file', new Blob([new Uint8Array(png)], { type: 'image/png' }), 'cover.png');

        return data;
      },
    }),
  );
}

async function makePublic(api: Api, repositoryId: string, text: string) {
  await ok(
    api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repositoryId } },
      body: {
        preview: 'showcase',
        breaking: false,
        acknowledge_breaking: true,
        accept_terms: true,
        summary: text,
        label: '1.0',
      },
    }),
  );
}

async function addMember(owner: Person, tenantId: string, person: Person, role: string) {
  await ok(
    owner.api.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: tenantId } },
      body: { user_id: person.me.id, role: role as 'owner' | 'orga' | 'author' },
    }),
  );
}

// A private repository with an entry in it, made by an Owner.
async function world() {
  const owner = await newUser('profile-owner', ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);

  await addItem(owner.api, repository.id, 'Owlbear');

  return { owner, repository, tag };
}

// What the PATCH of the page says is replaced by `body` on its way to the real API, so that the API's own
// refusal, and not the screen's, is what the test reads. The screen checks what it can before it sends.
async function sendInstead(page: Page, body: unknown) {
  await page.route('**/tenants/*/profile', async (route) => {
    if (route.request().method() === 'PATCH') {
      await route.continue({ postData: JSON.stringify(body) });
    } else {
      await route.fallback();
    }
  });
}

function watchWrites(page: Page, path: RegExp) {
  const writes: string[] = [];

  page.on('request', (request) => {
    if (['PUT', 'PATCH', 'POST', 'DELETE'].includes(request.method()) && path.test(request.url())) {
      writes.push(request.method());
    }
  });

  return writes;
}

test('an Owner fills every field, saves it as one request, reloads and sees it, and Discover shows it', async ({
  browser,
}) => {
  const { owner, repository, tag } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);
  const patches: unknown[] = [];

  page.on('request', (request) => {
    if (
      request.method() === 'PATCH' &&
      request.url().endsWith(`/tenants/${repository.id}/profile`)
    ) {
      patches.push(request.postDataJSON());
    }
  });

  await openProfile(page, repository.slug);

  // What it is for, and what no licence means.
  await expect(profilePanel(page)).toContainText(
    'What this repository says about itself. People read it on Discover before they copy it.',
  );
  await expect(profilePanel(page)).toContainText(
    'One or two lines that say what this repository is. People read it before they copy it.',
  );
  await expect(profilePanel(page)).toContainText('"No licence stated" is not a licence.');
  await expect(page.locator('#profile-licence')).toHaveValue('');
  await expect(saveButton(page)).toBeDisabled();
  await expect(revertButton(page)).toBeDisabled();

  await summary(page).fill(`Every beast  there is,\nwith its habits ${tag}.`);
  await expect(page.locator('[data-profile-summary-count]')).toHaveText(
    `${`Every beast there is, with its habits ${tag}.`.length} of 280`,
  );
  await expect(page.locator('[data-profile-status]')).toHaveText('You have unsaved changes.');
  await expect(saveButton(page)).toBeEnabled();

  // A listed licence brings its usual link.
  await page.locator('#profile-licence').selectOption('CC BY 4.0');
  await expect(page.locator('#profile-licence-link')).toHaveValue(
    'https://creativecommons.org/licenses/by/4.0/',
  );

  // Credits: add, edit, move, remove, and the cap said.
  await expect(page.locator('[data-credits-count]')).toHaveText('0 of 20 credits');
  await profilePanel(page).getByRole('button', { name: 'Add a credit' }).click();
  await creditRow(page, 0).getByLabel('Name', { exact: true }).fill('Bob Mapper');
  await creditRow(page, 0).getByLabel('What they did (optional)').fill('Maps');
  await profilePanel(page).getByRole('button', { name: 'Add a credit' }).click();
  await creditRow(page, 1).getByLabel('Name', { exact: true }).fill('Ada Writer');
  await creditRow(page, 1).getByLabel('What they did (optional)').fill('Writer');
  await creditRow(page, 1).getByLabel('Link (optional)').fill('https://ada.example/');
  await expect(page.locator('[data-credits-count]')).toHaveText('2 of 20 credits');
  await expect(creditRow(page, 0).getByRole('button', { name: 'Move up' })).toBeDisabled();
  await expect(creditRow(page, 1).getByRole('button', { name: 'Move down' })).toBeDisabled();
  await creditRow(page, 1).getByRole('button', { name: 'Move up' }).click();
  await expect(creditRow(page, 0).getByLabel('Name', { exact: true })).toHaveValue('Ada Writer');
  await expect(creditRow(page, 1).getByLabel('Name', { exact: true })).toHaveValue('Bob Mapper');
  await profilePanel(page).getByRole('button', { name: 'Add a credit' }).click();
  await creditRow(page, 2).getByLabel('Name', { exact: true }).fill('Nobody');
  await creditRow(page, 2).getByRole('button', { name: 'Remove' }).click();
  await expect(page.locator('[data-credit]')).toHaveCount(2);

  // Tags: chips in the form the API keeps, a repeat not added, removable.
  await page.locator('#profile-tag').fill(`Dark  Fantasy, Tag-${tag}`);
  await page.locator('#profile-tag').press('Enter');
  await page.locator('#profile-tag').fill('dark fantasy');
  await page.locator('#profile-tag').press('Enter');
  await page.locator('#profile-tag').fill('undead');
  await profilePanel(page).getByRole('button', { name: 'Add', exact: true }).first().click();
  await expect(page.locator('[data-tags-list] li')).toHaveCount(3);
  await expect(page.locator('[data-tags-list]')).toContainText('dark fantasy');
  await expect(page.locator('[data-tags-count]')).toHaveText('3 of 12 tags');
  await page.getByRole('button', { name: 'Remove the tag undead' }).click();
  await expect(page.locator('[data-tags-list] li')).toHaveCount(2);

  await page.locator('#profile-system').fill(`  System   ${tag} `);

  // Languages: codes, shown by name.
  await page.locator('#profile-language').fill('DE');
  await page.locator('#profile-language').press('Enter');
  await page.locator('#profile-language').fill('en');
  await page.locator('#profile-language').press('Enter');
  await expect(page.locator('[data-languages-list]')).toContainText('German (de)');
  await expect(page.locator('[data-languages-list]')).toContainText('English (en)');
  await expect(page.locator('[data-languages-count]')).toHaveText('2 of 8 languages');

  // What people will see follows the form before it is saved.
  const preview = page.locator('[data-profile-preview]');

  await expect(preview).toContainText('What people will see');
  await expect(page.locator('[data-preview-card]')).toContainText(
    `Every beast there is, with its habits ${tag}.`,
  );
  await expect(page.locator('[data-preview-card]')).toContainText(`tag-${tag}`);
  await expect(page.locator('[data-preview-card]')).toContainText(`System ${tag}`);
  await expect(preview.locator('dl')).toContainText('German (de), English (en)');
  await expect(preview.locator('dl')).toContainText('CC BY 4.0');
  await expect(preview.locator('dl')).toContainText('Ada Writer, Writer');

  expect(patches).toHaveLength(0);
  await saveButton(page).click();
  await expect(status(page)).toHaveText('Saved.');
  await expect(saveButton(page)).toBeDisabled();

  // One request of what changed, in the form the API keeps.
  expect(patches).toHaveLength(1);
  expect(patches[0]).toEqual({
    summary: `Every beast there is, with its habits ${tag}.`,
    licence: { label: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    credits: [
      { name: 'Ada Writer', role: 'Writer', url: 'https://ada.example/' },
      { name: 'Bob Mapper', role: 'Maps', url: null },
    ],
    tags: ['dark fantasy', `tag-${tag}`],
    system: `System ${tag}`,
    languages: ['de', 'en'],
  });

  const kept = await profileOf(owner.api, repository.id);

  expect(kept.summary).toBe(`Every beast there is, with its habits ${tag}.`);
  expect(kept.tags).toEqual(['dark fantasy', `tag-${tag}`]);
  expect(kept.languages).toEqual(['de', 'en']);

  // Edit one field: only that one is sent.
  await page.locator('#profile-system').fill(`System ${tag} 2`);
  await saveButton(page).click();
  await expect(status(page)).toHaveText('Saved.');
  expect(patches).toHaveLength(2);
  expect(patches[1]).toEqual({ system: `System ${tag} 2` });

  // Reload: it is all there.
  await openProfile(page, repository.slug);
  await expect(summary(page)).toHaveValue(`Every beast there is, with its habits ${tag}.`);
  await expect(page.locator('#profile-licence')).toHaveValue('CC BY 4.0');
  await expect(page.locator('#profile-licence-link')).toHaveValue(
    'https://creativecommons.org/licenses/by/4.0/',
  );
  await expect(creditRow(page, 0).getByLabel('Name', { exact: true })).toHaveValue('Ada Writer');
  await expect(creditRow(page, 1).getByLabel('Link (optional)')).toHaveValue('');
  await expect(page.locator('[data-tags-list]')).toContainText(`tag-${tag}`);
  await expect(page.locator('#profile-system')).toHaveValue(`System ${tag} 2`);
  await expect(page.locator('[data-languages-list]')).toContainText('German (de)');

  // Revert goes back to what is saved.
  await summary(page).fill('Something else');
  await revertButton(page).click();
  await expect(summary(page)).toHaveValue(`Every beast there is, with its habits ${tag}.`);
  await expect(saveButton(page)).toBeDisabled();

  // Public, Discover's listing and the repository's page say what was saved.
  await makePublic(owner.api, repository.id, `Every beast there is, with its habits ${tag}.`);
  await page.goto(`/discover/?q=${encodeURIComponent(`tag-${tag}`)}`);

  const card = page.locator('[data-results] > li').filter({ hasText: repository.name });

  await expect(card).toHaveCount(1);
  await expect(card).toContainText(`Every beast there is, with its habits ${tag}.`);
  await expect(card).toContainText('dark fantasy');
  await expect(card).toContainText(`System ${tag} 2`);

  await card.getByRole('link', { name: repository.name }).click();

  const storefront = page.locator('[data-storefront]');

  await expect(storefront).toContainText('German (de), English (en)');
  await expect(storefront.locator('[data-licence]')).toContainText('CC BY 4.0');
  await expect(storefront.locator('[data-licence] a')).toHaveAttribute(
    'href',
    'https://creativecommons.org/licenses/by/4.0/',
  );
  await expect(storefront.locator('[data-credits]')).toContainText('Ada Writer');
  await expect(storefront.locator('[data-credits]')).toContainText('Bob Mapper');
  expect(await page.locator('body').innerText()).not.toMatch(/tenant|grant|subscri/i);
  await context.close();
});

test('a link that is not https is refused in the screen first, in the API words, and sends nothing', async ({
  browser,
}) => {
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);
  const writes = watchWrites(page, new RegExp(`/tenants/${repository.id}/profile$`));

  await openProfile(page, repository.slug);
  await summary(page).fill('Kept only if it all passes.');
  await page.locator('#profile-licence').selectOption('Other…');
  await page.locator('#profile-licence-other').fill('House rules');
  await page.locator('#profile-licence-link').fill('http://example.com/rules');
  await profilePanel(page).getByRole('button', { name: 'Add a credit' }).click();
  await creditRow(page, 0).getByLabel('Name', { exact: true }).fill('Ada');
  await creditRow(page, 0).getByLabel('Link (optional)').fill('javascript:alert(1)');

  await saveButton(page).click();
  await expect(problem(page, 'licenceLink')).toHaveText('A link must start with https://');
  await expect(creditRow(page, 0).locator('[data-problem]').nth(2)).toHaveText(
    'A link must start with https://',
  );
  await expect(page.locator('#profile-licence-link')).toBeFocused();
  expect(writes).toEqual([]);
  expect((await profileOf(owner.api, repository.id)).summary).toBe('');

  // Taking the problem back as soon as the field is fixed.
  await page.locator('#profile-licence-link').fill('https://example.com/rules');
  await expect(problem(page, 'licenceLink')).toBeHidden();
  await context.close();
});

test('a summary that is too long and a thirteenth tag are said in words next to the field, and nothing is sent', async ({
  browser,
}) => {
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);
  const writes = watchWrites(page, new RegExp(`/tenants/${repository.id}/profile$`));

  await openProfile(page, repository.slug);
  await summary(page).fill('x'.repeat(300));
  await expect(page.locator('[data-profile-summary-count]')).toHaveText('300 of 280');
  await saveButton(page).click();
  await expect(problem(page, 'summary')).toHaveText(
    'A summary is at most 280 characters. This one is 300.',
  );
  await expect(summary(page)).toBeFocused();
  await summary(page).fill('Fine now.');

  for (let index = 0; index < 12; index++) {
    await page.locator('#profile-tag').fill(`tag${index}`);
    await page.locator('#profile-tag').press('Enter');
  }

  await expect(page.locator('[data-tags-count]')).toHaveText('12 of 12 tags');
  await page.locator('#profile-tag').fill('one more');
  await page.locator('#profile-tag').press('Enter');
  await expect(problem(page, 'tags')).toHaveText('At most 12 tags');
  await expect(page.locator('[data-tags-list] li')).toHaveCount(12);

  await page.locator('#profile-tag').fill('x'.repeat(33));
  await page.locator('#profile-tag').press('Enter');
  await expect(problem(page, 'tags')).toHaveText('A tag is at most 32 characters');

  await page.locator('#profile-language').fill('German');
  await page.locator('#profile-language').press('Enter');
  await expect(problem(page, 'languages')).toHaveText(
    "'German' isn't a language code such as en, de or pt-br",
  );

  expect(writes).toEqual([]);
  expect((await profileOf(owner.api, repository.id)).summary).toBe('');
  await context.close();
});

test('what the API refuses is shown in its words next to the field it names, and it keeps nothing', async ({
  browser,
}) => {
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: { summary: 'The old summary.', tags: ['old'] },
    }),
  );
  await openProfile(page, repository.slug);
  // A licence chosen, so that its link has a field.
  await page.locator('#profile-licence').selectOption('CC0 1.0');

  // The screen sends something it accepts; what reaches the API is not that, so that the API's refusal
  // is what is read: an http link, a summary over the limit, and too many tags.
  const cases: { body: unknown; key: string; words: string }[] = [
    {
      body: { summary: 'New', licence: { label: 'CC0 1.0', url: 'http://example.com' } },
      key: 'licenceLink',
      words: 'A link must start with https://',
    },
    {
      body: { summary: 'x'.repeat(300) },
      key: 'summary',
      words: 'A summary is at most 280 characters',
    },
    {
      body: { tags: Array.from({ length: 13 }, (_, index) => `tag${index}`) },
      key: 'tags',
      words: 'At most 12 tags',
    },
  ];

  for (const [position, { body, key, words }] of cases.entries()) {
    await page.unroute('**/tenants/*/profile');
    await sendInstead(page, body);
    await summary(page).fill(`A summary ${position}`);
    await saveButton(page).click();

    await expect(problem(page, key)).toContainText(words);

    // Nothing was kept, not even what in the request was fine.
    const kept = await profileOf(owner.api, repository.id);

    expect(kept.summary).toBe('The old summary.');
    expect(kept.tags).toEqual(['old']);
    expect(kept.licence).toBeNull();
    expect(kept.credits).toEqual([]);
    // And what was typed is still in the form, to fix.
    await expect(summary(page)).toHaveValue(`A summary ${position}`);
  }

  // A credit's link, named by where it is in the request.
  await page.unroute('**/tenants/*/profile');
  await profilePanel(page).getByRole('button', { name: 'Add a credit' }).click();
  await creditRow(page, 0).getByLabel('Name', { exact: true }).fill('Ada');
  await sendInstead(page, { credits: [{ name: 'Ada', url: 'http://ada.example' }] });
  await saveButton(page).click();
  await expect(creditRow(page, 0).locator('[data-problem]').nth(2)).toHaveText(
    'A link must start with https://',
  );
  expect((await profileOf(owner.api, repository.id)).credits).toEqual([]);

  // A refusal that names no field is said as one sentence above the buttons.
  await page.unroute('**/tenants/*/profile');
  await page.route('**/tenants/*/profile', async (route) => {
    if (route.request().method() === 'PATCH') {
      await route.fulfill({
        status: 403,
        contentType: 'application/problem+json',
        body: JSON.stringify({
          type: 'repository-management-forbidden',
          title: 'Only an Owner',
          status: 403,
          detail: 'Only an Owner of the repository may change this.',
        }),
      });
    } else {
      await route.fallback();
    }
  });
  await saveButton(page).click();
  await expect(problem(page, 'form')).toHaveText(
    'Only an Owner of the repository may change this.',
  );
  await context.close();
});

test('a repository with no cover says what Discover shows, takes one after a look, replaces it and removes it after asking', async ({
  browser,
}) => {
  const { owner, repository } = await world();
  const { page, context, confirmations } = await signedInPage(browser, owner.subject);
  const writes = watchWrites(page, new RegExp(`/tenants/${repository.id}/profile/cover$`));
  const asked: { token: boolean }[] = [];

  page.on('request', (request) => {
    if (
      request.url().includes(`/tenants/${repository.id}/profile/cover`) &&
      request.method() === 'GET'
    ) {
      asked.push({ token: Boolean(request.headers().authorization) });
    }
  });

  await openProfile(page, repository.slug);
  await expect(cover(page)).toContainText('No cover yet.');
  await expect(cover(page)).toContainText(
    'In the list Discover shows the first letter of the repository’s name instead',
  );
  await expect(cover(page)).toContainText('PNG, JPEG, WebP or GIF, up to 10 MB.');
  await expect(cover(page).getByRole('button', { name: 'Choose a picture…' })).toBeVisible();
  await expect(cover(page).getByRole('button', { name: 'Remove the cover' })).toBeHidden();
  // The first letter, as Discover draws it.
  await expect(cover(page).locator('[data-cover-initial]')).toHaveText('B');

  // A file the API would refuse is told in the browser: nothing is sent.
  await cover(page)
    .locator('[data-cover-file]')
    .setInputFiles({
      name: 'notes.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('not a picture'),
    });
  await expect(cover(page).locator('[data-cover-status]')).toContainText(
    "That file type won't work. Use a PNG, JPEG, WebP or GIF.",
  );
  await expect(cover(page).locator('[data-cover-staged]')).toBeHidden();
  expect(writes).toEqual([]);

  // A picture chosen is looked at first: nothing is uploaded until Upload.
  await cover(page).locator('[data-cover-file]').setInputFiles({
    name: 'cover.png',
    mimeType: 'image/png',
    buffer: BLUE,
  });
  await expect(cover(page).locator('[data-cover-staged]')).toBeVisible();
  // The preview is drawn from the file itself: the canvas has pixels in it.
  await expect
    .poll(() =>
      cover(page)
        .locator('canvas[data-cover-staged-picture]')
        .evaluate((canvas: HTMLCanvasElement) => {
          const data = canvas.getContext('2d')?.getImageData(0, 0, 1, 1).data;

          return data ? data[3] : 0;
        }),
    )
    .toBeGreaterThan(0);
  await expect(cover(page)).toContainText(
    'This is how it will look. Upload it to use it as the cover, or cancel.',
  );
  expect(writes).toEqual([]);
  expect((await profileOf(owner.api, repository.id)).has_cover).toBe(false);

  await cover(page).getByRole('button', { name: 'Cancel' }).click();
  await expect(cover(page).locator('[data-cover-staged]')).toBeHidden();
  expect((await profileOf(owner.api, repository.id)).has_cover).toBe(false);

  await cover(page).locator('[data-cover-file]').setInputFiles({
    name: 'cover.png',
    mimeType: 'image/png',
    buffer: BLUE,
  });
  await cover(page).getByRole('button', { name: 'Upload' }).click();
  await expect(cover(page).locator('[data-cover-status]')).toHaveText('The cover was updated.');
  await expect(cover(page).locator('[data-cover-picture]')).toBeVisible();
  await expect(cover(page).locator('[data-cover-picture]')).toHaveAttribute('src', /^blob:/);
  await expect(cover(page).locator('[data-cover-none]')).toBeHidden();
  expect(writes).toEqual(['PUT']);
  expect((await profileOf(owner.api, repository.id)).has_cover).toBe(true);

  // The cover is in what people will see.
  await expect(page.locator('[data-profile-preview] [data-picture]')).toBeVisible();

  // Replace it, and see the new one.
  const first = await cover(page).locator('[data-cover-picture]').getAttribute('src');

  await expect(cover(page).getByRole('button', { name: 'Replace the picture…' })).toBeVisible();
  await cover(page).locator('[data-cover-file]').setInputFiles({
    name: 'second.png',
    mimeType: 'image/png',
    buffer: GREEN,
  });
  await cover(page).getByRole('button', { name: 'Upload' }).click();
  await expect(cover(page).locator('[data-cover-status]')).toHaveText('The cover was updated.');
  await expect
    .poll(async () => cover(page).locator('[data-cover-picture]').getAttribute('src'))
    .not.toBe(first);
  expect(writes).toEqual(['PUT', 'PUT']);

  // The cover is fetched with the token (ADR 0300): the repository is private.
  expect(asked.length).toBeGreaterThan(0);
  expect(asked.every((request) => request.token)).toBe(true);

  // After a public release its page shows it.
  await makePublic(owner.api, repository.id, 'A repository with a cover.');
  await page.goto(`/discover/?repository=${repository.id}`);
  await expect(page.locator('[data-storefront] [data-cover]')).toBeVisible();
  await expect(page.locator('[data-storefront] [data-cover]')).toHaveAttribute('src', /^blob:/);
  await openProfile(page, repository.slug);

  // Remove asks first, and says what Discover shows after.
  expect(confirmations).toEqual([]);
  await cover(page).getByRole('button', { name: 'Remove the cover' }).click();
  await expect(cover(page).locator('[data-cover-status]')).toHaveText('The cover was removed.');
  expect(confirmations).toEqual([
    'Remove the cover? Discover will show the first letter of the repository’s name instead.',
  ]);
  await expect(cover(page)).toContainText('No cover yet.');
  await expect(cover(page).locator('[data-cover-picture]')).toBeHidden();
  expect((await profileOf(owner.api, repository.id)).has_cover).toBe(false);
  expect(writes).toEqual(['PUT', 'PUT', 'DELETE']);
  await context.close();
});

test('a refused cover keeps the picture to choose another, and a cancelled removal keeps the cover', async ({
  browser,
}) => {
  const { owner, repository } = await world();

  await setCover(owner.api, repository.id, BLUE);

  const { page, context } = await signedInPage(browser, owner.subject);

  await openProfile(page, repository.slug);
  await expect(cover(page).locator('[data-cover-picture]')).toBeVisible();

  // The API refuses an upload: its words are said and the picture stays chosen.
  await page.route('**/tenants/*/profile/cover', async (route) => {
    if (route.request().method() === 'PUT') {
      await route.fulfill({
        status: 422,
        contentType: 'application/problem+json',
        body: JSON.stringify({
          type: 'invalid-profile-picture',
          title: 'Invalid profile picture',
          status: 422,
          detail: 'The picture is larger than this server accepts.',
        }),
      });
    } else {
      await route.fallback();
    }
  });
  await cover(page).locator('[data-cover-file]').setInputFiles({
    name: 'big.png',
    mimeType: 'image/png',
    buffer: GREEN,
  });
  await cover(page).getByRole('button', { name: 'Upload' }).click();
  await expect(cover(page).locator('[data-cover-status]')).toHaveText(
    'The picture is larger than this server accepts.',
  );
  await expect(cover(page).locator('[data-cover-staged]')).toBeVisible();
  await page.unroute('**/tenants/*/profile/cover');

  // A removal said no to keeps it.
  await cover(page).getByRole('button', { name: 'Cancel' }).click();
  page.removeAllListeners('dialog');
  page.once('dialog', (dialog) => void dialog.dismiss());
  await cover(page).getByRole('button', { name: 'Remove the cover' }).click();
  await expect(cover(page).locator('[data-cover-picture]')).toBeVisible();
  expect((await profileOf(owner.api, repository.id)).has_cover).toBe(true);
  await context.close();
});

test('an Organizer and an Author read the profile and cannot change it, as the API has it', async ({
  browser,
}) => {
  const { owner, repository, tag } = await world();
  const organizer = await newUser('profile-orga');
  const author = await newUser('profile-author');

  await addMember(owner, repository.id, organizer, 'orga');
  await addMember(owner, repository.id, author, 'author');
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: {
        summary: `Written by the Owner ${tag}`,
        tags: ['monsters'],
        system: 'D&D 5e',
        licence: { label: 'CC0 1.0', url: null },
      },
    }),
  );
  await setCover(owner.api, repository.id, BLUE);

  // The API refuses an Organizer, so the screen has no inputs for one.
  const refused = await organizer.api.PATCH('/tenants/{tenant_id}/profile', {
    params: { path: { tenant_id: repository.id } },
    body: { summary: 'Mine' },
  });

  expect(refused.response.status).toBe(403);
  expect((await profileOf(owner.api, repository.id)).summary).toBe(`Written by the Owner ${tag}`);

  for (const person of [organizer, author]) {
    const { page, context } = await signedInPage(browser, person.subject);

    await openProfile(page, repository.slug);
    await expect(profilePanel(page)).toContainText('Only an Owner can change this.');
    await expect(page.locator('[data-profile-form]')).toBeHidden();
    await expect(
      profilePanel(page).locator('input:visible, textarea:visible, select:visible'),
    ).toHaveCount(0);
    await expect(profilePanel(page).getByRole('button')).toHaveCount(0);

    // What it says, read.
    const preview = page.locator('[data-profile-preview]');

    await expect(page.locator('[data-preview-card]')).toContainText(`Written by the Owner ${tag}`);
    await expect(page.locator('[data-preview-card]')).toContainText('monsters');
    await expect(page.locator('[data-preview-card]')).toContainText('D&D 5e');
    await expect(preview.locator('dl')).toContainText('CC0 1.0');
    await expect(cover(page).locator('[data-cover-picture]')).toBeVisible();
    await expect(cover(page).locator('[data-cover-buttons]')).toBeHidden();
    await context.close();
  }
});

test('before it can be public: what is missing, each a link that jumps to the field', async ({
  browser,
}) => {
  const { owner, repository, tag } = await world();
  const other = await newUser('upstream-owner', ['tenant_creator']);
  const theirs = await newRepository(other.api, `Theirs ${tag}`);
  const core = await newRepository(owner.api, `Core ${tag}`);

  // Built on one that is not public, owned by somebody else, and one that is the Owner's.
  await addItem(other.api, theirs.id, 'Shield');
  await addItem(owner.api, core.id, 'Longsword');
  await publish(other.api, theirs.id);
  await publish(owner.api, core.id);
  await invite(other.api, theirs.id, repository.id);
  await invite(owner.api, core.id, repository.id);

  for (const upstream of [theirs, core]) {
    await ok(
      owner.api.POST('/tenants/{tenant_id}/repositories/{repository_id}/copy', {
        params: { path: { tenant_id: repository.id, repository_id: upstream.id } },
        body: {},
      }),
    );
  }

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();

  const list = page.locator('[data-readiness]');

  await expect(list).toBeVisible();
  await expect(list.getByRole('heading', { name: 'Before this can be public' })).toBeVisible();
  await expect(list).toContainText(
    'It needs a summary. A repository cannot be made public without one.',
  );
  await expect(list).toContainText(
    'A cover is not required, but it is the first thing people see.',
  );
  await expect(list).toContainText(`${theirs.name} is not public.`);
  await expect(list).toContainText(`${core.name} is not public.`);
  await expect(list).toContainText('ask its Owner to make it public');
  await expect(list).toContainText(
    'The Make public dialog checks it again before it changes anything.',
  );
  expect(await list.innerText()).not.toMatch(/tenant|grant|subscri/i);

  // Needed, and recommended, as pills.
  await expect(list.locator('[data-need="required"][data-done="false"]')).toHaveCount(3);
  await expect(list.locator('[data-need="recommended"][data-done="false"]')).toHaveCount(1);

  // The summary link opens the tab and puts the cursor in the field.
  await list.getByRole('link', { name: 'Write the summary' }).click();
  await expect(page.getByRole('tab', { name: 'Profile' })).toHaveAttribute('aria-selected', 'true');
  await expect(summary(page)).toBeFocused();

  // Write it, and the list says so after Save.
  await summary(page).fill('Beasts for the table.');
  await saveButton(page).click();
  await expect(status(page)).toHaveText('Saved.');
  await page.getByRole('tab', { name: 'Overview' }).click();
  await expect(list.locator('[data-need="required"][data-done="true"]').first()).toContainText(
    'It has a summary.',
  );
  await expect(list).not.toContainText('It needs a summary');

  // The cover link, and the cover done once there is one.
  await list.getByRole('link', { name: 'Add a cover' }).click();
  await expect(page.getByRole('tab', { name: 'Profile' })).toHaveAttribute('aria-selected', 'true');
  await expect(cover(page).getByRole('button', { name: 'Choose a picture…' })).toBeFocused();
  await cover(page).locator('[data-cover-file]').setInputFiles({
    name: 'cover.png',
    mimeType: 'image/png',
    buffer: BLUE,
  });
  await cover(page).getByRole('button', { name: 'Upload' }).click();
  await expect(cover(page).locator('[data-cover-status]')).toHaveText('The cover was updated.');
  await page.getByRole('tab', { name: 'Overview' }).click();
  await expect(list).toContainText('It has a cover.');
  await expect(list.locator('[data-need="recommended"][data-done="true"]')).toHaveCount(1);

  // The upstream that is not the Owner's: a link to Built on. The one that is: its own page.
  await list.getByRole('link', { name: 'Open Built on' }).first().click();
  await expect(page.getByRole('tab', { name: 'Built on' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.getByRole('tab', { name: 'Overview' }).click();
  await expect(
    list.getByRole('link', { name: `Open ${core.name} to make it public` }),
  ).toHaveAttribute('href', `/studio/?repository=${core.id}`);

  // The flip's own rules stand: the dialog still lists what stands in the way.
  await page.locator('[data-visibility]').getByRole('button', { name: 'Make public…' }).click();
  await expect(page.locator('[data-vis-blockers]')).toContainText(`${theirs.name} is not public.`);
  await context.close();
});

test('a repository with everything ready says so, and a public one has no list', async ({
  browser,
}) => {
  const { owner, repository } = await world();

  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: { summary: 'All ready.' },
    }),
  );
  await setCover(owner.api, repository.id, BLUE);

  const { page, context } = await signedInPage(browser, owner.subject);

  await page.goto(`/studio/?repository=${repository.slug}`);

  const list = page.locator('[data-readiness]');

  await expect(list).toBeVisible();
  await expect(list).toContainText('It has a summary.');
  await expect(list).toContainText('It has a cover.');
  await expect(list).toContainText('Everything it is built on is public and up to date.');
  await expect(list.locator('[data-done="false"]')).toHaveCount(0);

  await makePublic(owner.api, repository.id, 'All ready.');
  await page.reload();
  await expect(page.locator('[data-visibility-state]')).toHaveText('Public');
  await expect(list).toBeHidden();
  await context.close();
});

test('the Make public dialog starts from the saved summary, with the help and the count of the Profile tab', async ({
  browser,
}) => {
  const { owner, repository } = await world();
  const { page, context } = await signedInPage(browser, owner.subject);

  await openProfile(page, repository.slug);
  await summary(page).fill('Saved on the Profile tab.');
  await saveButton(page).click();
  await expect(status(page)).toHaveText('Saved.');
  await page.getByRole('tab', { name: 'Overview' }).click();
  await page.locator('[data-visibility]').getByRole('button', { name: 'Make public…' }).click();

  const dialog = page.locator('[data-visibility-dialog]');

  await expect(dialog).toBeVisible();
  await expect(dialog.locator('[data-vis-summary]')).toHaveValue('Saved on the Profile tab.');

  // One helper: the same help and the same count, in the same words.
  const help = await page.locator('[data-profile-summary-help]').textContent();

  await expect(dialog.locator('[data-vis-summary-help]')).toHaveText(help ?? '');
  await expect(dialog.locator('[data-vis-summary-count]')).toHaveText('25 of 280');
  await dialog.locator('[data-vis-summary]').fill('y'.repeat(285));
  await expect(dialog.locator('[data-vis-summary-count]')).toHaveText('285 of 280');
  await dialog.getByRole('button', { name: 'Cancel' }).click();

  // What the dialog sends is the profile's: after it is public, the Profile tab shows the summary the
  // dialog wrote.
  await page.locator('[data-visibility]').getByRole('button', { name: 'Make public…' }).click();
  await dialog.locator('[data-vis-summary]').fill('Written in the dialog.');
  await dialog.getByRole('textbox', { name: /^Label/ }).fill('First');
  await dialog.getByRole('checkbox', { name: /^I have the right to publish/ }).check();
  await dialog.getByRole('button', { name: 'Make public and publish release' }).click();
  await expect(page.locator('[data-visibility-state]')).toHaveText('Public');
  await page.getByRole('tab', { name: 'Profile' }).click();
  await expect(summary(page)).toHaveValue('Written in the dialog.');
  await context.close();
});

test('leaving the Profile tab with something unsaved asks first, and a saved one asks nothing', async ({
  browser,
}) => {
  const { owner, repository } = await world();
  const { page, context, confirmations } = await signedInPage(browser, owner.subject);

  await openProfile(page, repository.slug);

  // Said no to: it stays, with what was typed.
  await summary(page).fill('Not saved yet.');
  page.removeAllListeners('dialog');
  page.once('dialog', (dialog) => {
    confirmations.push(dialog.message());
    void dialog.dismiss();
  });
  await page.getByRole('tab', { name: 'Overview' }).click();
  expect(confirmations).toEqual([
    'You have unsaved changes to the profile. Leave without saving them?',
  ]);
  await expect(page.getByRole('tab', { name: 'Profile' })).toHaveAttribute('aria-selected', 'true');
  await expect(summary(page)).toHaveValue('Not saved yet.');

  // Said yes to: it leaves, and what was typed comes back when the tab is opened again.
  page.once('dialog', (dialog) => {
    confirmations.push(dialog.message());
    void dialog.accept();
  });
  await page.getByRole('tab', { name: 'Overview' }).click();
  await expect(page.getByRole('tab', { name: 'Overview' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.getByRole('tab', { name: 'Profile' }).click();
  await expect(summary(page)).toHaveValue('Not saved yet.');
  expect(confirmations).toHaveLength(2);

  // Saved, it asks nothing.
  await saveButton(page).click();
  await expect(status(page)).toHaveText('Saved.');
  await page.getByRole('tab', { name: 'People' }).click();
  await expect(page.getByRole('tab', { name: 'People' })).toHaveAttribute('aria-selected', 'true');
  expect(confirmations).toHaveLength(2);

  // Another repository from the list asks too.
  const second = await newRepository(owner.api, `Second ${crypto.randomUUID().slice(0, 8)}`);

  await page.reload();
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
  await page.getByRole('tab', { name: 'Profile' }).click();
  await summary(page).fill('Changed again.');
  page.once('dialog', (dialog) => {
    confirmations.push(dialog.message());
    void dialog.dismiss();
  });
  await page.locator('[data-list]').getByRole('link', { name: second.name }).click();
  expect(confirmations).toHaveLength(3);
  await expect(page.locator('h2[data-name]')).toHaveText(repository.name);
  await context.close();
});

test('on a phone, the Profile tab is one column, nothing overflows and everything pressed is big enough', async ({
  browser,
}) => {
  const { owner, repository } = await world();

  await setCover(owner.api, repository.id, BLUE);
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repository.id } },
      body: {
        summary:
          'A summary that is long enough to wrap on a phone, with a few more words to be sure.',
        tags: ['monsters', 'undead', 'a-rather-long-tag-that-is-fine'],
        languages: ['de', 'en'],
        licence: { label: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
        credits: [
          { name: 'Ada Writer', role: 'Writer', url: 'https://ada.example/a/long/address' },
        ],
      },
    }),
  );

  const { page, context } = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 812 },
  });

  await openProfile(page, repository.slug);
  await expect(cover(page).locator('[data-cover-picture]')).toBeVisible();
  await profilePanel(page).getByRole('button', { name: 'Add a credit' }).click();
  await cover(page).locator('[data-cover-file]').setInputFiles({
    name: 'cover.png',
    mimeType: 'image/png',
    buffer: GREEN,
  });
  await expect(cover(page).locator('[data-cover-staged]')).toBeVisible();

  const measures = async () =>
    page.evaluate(() => {
      const panel = document.querySelector('[data-profile]');
      const small: string[] = [];

      for (const element of panel?.querySelectorAll<HTMLElement>(
        'button, select, input:not([type="file"]), textarea, a',
      ) ?? []) {
        const box = element.getBoundingClientRect();

        // Hidden things take no room.
        if (box.width === 0 || box.height === 0) continue;
        // A textarea is as tall as its rows; every other control is at least a thumb.
        if (element.tagName !== 'TEXTAREA' && box.height < 44) {
          small.push(`${element.tagName} ${element.textContent?.slice(0, 20) ?? ''} ${box.height}`);
        }
        if (box.left < 0 || box.right > window.innerWidth + 0.5) {
          small.push(`outside ${element.tagName} ${box.left} ${box.right}`);
        }
      }

      return {
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        small,
      };
    });

  const measured = await measures();

  expect(measured.overflow).toBeLessThanOrEqual(0);
  expect(measured.small).toEqual([]);

  // The same with the readiness list and the visibility card on the Overview.
  await page.getByRole('tab', { name: 'Overview' }).click();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth),
  ).toBeLessThanOrEqual(0);
  await context.close();

  // A member who only reads it sees the same width.
  const author = await newUser('profile-author');

  await addMember(owner, repository.id, author, 'author');

  const reader = await signedInPage(browser, author.subject, {
    viewport: { width: 375, height: 812 },
  });

  await openProfile(reader.page, repository.slug);
  expect(
    await reader.page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth),
  ).toBeLessThanOrEqual(0);
  await reader.context.close();
});
