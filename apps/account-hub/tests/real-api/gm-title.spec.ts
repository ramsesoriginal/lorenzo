// What a table calls its game master (ADR 0294): set in the campaign's settings, read wherever that
// campaign appears, and "GM" wherever no one campaign is in play.
import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import {
  AUTHGEAR_URL,
  SITE_URL,
  SUBJECT_COOKIE,
} from '../../../inventory-web/tests/e2e/support/env';
import {
  addItem,
  addPlayer,
  campaignCard,
  makeGm,
  newCampaign,
  newLibrary,
  newRepository,
  newUser,
  openLibrary,
  signedInPage,
} from './support';

// What a person reads, with no literal GM in it.
const LITERAL_GM = /\bGMs?\b/;

// A campaign you run, found by the name it starts with.
function runCampaign(page: Page, name: string) {
  return page.locator('[data-run-list] > [data-run-campaign]').filter({ hasText: name });
}

test("a table's own word for its game master is read wherever its campaign appears", async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const zorro = await newCampaign(owner.api, library.id, 'Zorro');
  const hood = await newCampaign(owner.api, library.id, 'Hood');
  await makeGm(owner.api, library.id, zorro.id, owner.me.id);
  await makeGm(owner.api, library.id, hood.id, owner.me.id);
  const path = { tenant_id: library.id, campaign_id: zorro.id };
  const read = async () =>
    ok(owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}', { params: { path } }));

  // Every campaign has the default, set by the API.
  const before = await read();
  expect([before.gm_title, before.gm_title_plural]).toEqual(['GM', 'GMs']);

  const session = await signedInPage(browser, owner.subject);
  const { page } = session;
  const card = campaignCard(await openLibrary(page, library), 'Zorro');

  // The settings: two plain boxes, the default as their placeholders, and what they do not change.
  await card.getByRole('button', { name: 'Edit', exact: true }).click();
  const title = card.locator('[data-campaign-form]').getByLabel('Title', { exact: true });
  const plural = card.locator('[data-campaign-form]').getByLabel('Plural', { exact: true });
  await expect(card.getByText('What does your table call its game master?')).toBeVisible();
  await expect(title).toHaveValue('');
  await expect(title).toHaveAttribute('placeholder', 'GM');
  await expect(plural).toHaveAttribute('placeholder', 'GMs');
  await expect(title).toHaveAttribute('maxlength', '30');
  await expect(
    card.getByText('Shown wherever this campaign appears. It does not change what a GM may do.'),
  ).toBeVisible();
  await title.fill('Storyteller');
  await plural.fill('Storytellers');
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(card.locator('[data-campaign-meta]')).toContainText('Storyteller');

  const after = await read();
  expect([after.gm_title, after.gm_title_plural]).toEqual(['Storyteller', 'Storytellers']);

  // The campaign's own page: its row, its people, GM management, its roster.
  await expect(card.locator('[data-campaign-meta]')).toContainText('test · Storyteller');
  await expect(card.getByText('Assign someone as Storyteller:')).toBeVisible();
  await expect(card.getByText('Storytellers:', { exact: true })).toBeVisible();
  await expect(card.locator('[data-campaign-roster] .badge')).toHaveText('Storyteller');
  await expect(card.getByRole('button', { name: 'Step down as Storyteller' })).toBeVisible();

  // Its invite links: the button, the label, the one-use notice and the list.
  await card.getByRole('tab', { name: 'Invite links' }).click();
  const panel = card.locator('[data-invite-links]');
  await expect(panel.getByText('Storyteller link expires in')).toBeVisible();
  await panel.getByRole('button', { name: 'Invite someone to run it' }).click();
  await expect(panel.getByLabel('Storyteller invite link')).toHaveValue(
    new RegExp(`^${SITE_URL}/join/#`),
  );
  await expect(panel).toContainText('joins the Storytellers of this campaign');
  await expect(
    panel.locator('[data-list] > li').filter({ hasText: 'Storyteller link' }),
  ).toHaveCount(1);
  expect(await panel.innerText()).not.toMatch(LITERAL_GM);

  // Nothing on its card is left saying GM.
  expect(await card.innerText()).not.toMatch(LITERAL_GM);

  // The index of what you run: this campaign by its word, the other by the default.
  await page.goto('/campaigns');
  await expect(page.locator('#loading')).toBeHidden();
  const zorroRow = runCampaign(page, 'Zorro');
  await expect(zorroRow.locator('[data-meta]')).toContainText('Storyteller');
  await expect(zorroRow.getByRole('heading', { name: 'Storytellers' })).toBeVisible();
  expect(await zorroRow.innerText()).not.toMatch(LITERAL_GM);
  const hoodRow = runCampaign(page, 'Hood');
  await expect(hoodRow.locator('[data-meta]')).toContainText('GM');
  await expect(hoodRow.getByRole('heading', { name: 'GMs' })).toBeVisible();

  // A repository has no campaign: its publish dialog still says GM only.
  const repository = await newRepository(owner.api, `Bestiary ${crypto.randomUUID().slice(0, 8)}`);
  await addItem(owner.api, repository.id, 'Owlbear');
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(`/studio/?repository=${repository.slug}`);
  await expect(page.locator('[data-overview] [data-state]')).toBeVisible();
  await page.getByRole('button', { name: 'Publish…', exact: true }).click();
  await expect(page.locator('[data-publish-dialog]')).toContainText(
    'Notes marked GM only are copied along',
  );

  // Back to the default: both boxes empty.
  const again = campaignCard(await openLibrary(page, library), 'Zorro');
  await again.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(
    again.locator('[data-campaign-form]').getByLabel('Title', { exact: true }),
  ).toHaveValue('Storyteller');
  await again.locator('[data-campaign-form]').getByLabel('Title', { exact: true }).fill('');
  await again.locator('[data-campaign-form]').getByLabel('Plural', { exact: true }).fill('');
  await again.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(again.locator('[data-campaign-meta]')).toContainText('test · GM');
  const reset = await read();
  expect([reset.gm_title, reset.gm_title_plural]).toEqual(['GM', 'GMs']);
  await session.context.close();
});

test('a title is refused in words, whether the page or the API refuses it', async ({ browser }) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const zorro = await newCampaign(owner.api, library.id, 'Zorro');
  await makeGm(owner.api, library.id, zorro.id, owner.me.id);
  const path = { tenant_id: library.id, campaign_id: zorro.id };
  const read = async () =>
    ok(owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}', { params: { path } }));
  const words =
    'Give both, as plain text of at most 30 characters: letters, numbers, spaces and the punctuation of a name.';

  const session = await signedInPage(browser, owner.subject);
  const card = campaignCard(await openLibrary(session.page, library), 'Zorro');
  const status = card.locator('[data-campaign-form] [data-status]');

  await card.getByRole('button', { name: 'Edit', exact: true }).click();

  // One without the other.
  await card
    .locator('[data-campaign-form]')
    .getByLabel('Title', { exact: true })
    .fill('Storyteller');
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(status).toHaveText(words);

  // Markup is the API's to refuse, and is said with the same words.
  await card
    .locator('[data-campaign-form]')
    .getByLabel('Title', { exact: true })
    .fill('<b>Teller</b>');
  await card.locator('[data-campaign-form]').getByLabel('Plural', { exact: true }).fill('Tellers');
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(status).toHaveText(words);
  await expect(status).not.toContainText('{');

  const kept = await read();
  expect([kept.gm_title, kept.gm_title_plural]).toEqual(['GM', 'GMs']);

  // A name with an apostrophe and a space is plain text, kept as written.
  await card
    .locator('[data-campaign-form]')
    .getByLabel('Title', { exact: true })
    .fill("Keeper o' Tales");
  await card
    .locator('[data-campaign-form]')
    .getByLabel('Plural', { exact: true })
    .fill("Keepers o' Tales");
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(card.locator('[data-campaign-meta]')).toContainText("Keeper o' Tales");
  expect((await read()).gm_title).toBe("Keeper o' Tales");
  await session.context.close();
});

test('someone who joins a campaign by its game master link is told by its own word', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Zorro');
  const path = { tenant_id: library.id, campaign_id: campaign.id };
  await ok(
    owner.api.PATCH('/tenants/{tenant_id}/campaigns/{campaign_id}', {
      params: { path },
      body: { gm_title: 'Narrator', gm_title_plural: 'Narrators' },
    }),
  );
  const made = await ok(
    owner.api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/invites', {
      params: { path },
      body: { expires_at: new Date(Date.now() + 24 * 3_600_000).toISOString(), role: 'gm' },
    }),
  );
  const newcomer = await newUser('newcomer');

  const context = await browser.newContext();
  const page = await context.newPage();
  await context.addCookies([{ name: SUBJECT_COOKIE, value: newcomer.subject, url: AUTHGEAR_URL }]);
  await page.goto(`${SITE_URL}/join/#${made.token}`);
  // Before joining, the page does not know the campaign's word: it says GM.
  await expect(page.locator('[data-offer]')).toHaveText(
    "You've been invited to run this campaign as a GM.",
  );
  await page.getByRole('button', { name: 'Log in to join' }).click();
  await expect(page).toHaveURL(`${SITE_URL}/join/`);
  await page.getByRole('button', { name: 'Join as a GM', exact: true }).click();
  // Once it is theirs to read, it says the campaign's own.
  await expect(page.locator('[data-join] [data-status]')).toHaveText(
    "You're in. Zorro lists you among its Narrators.",
  );
  await context.close();
});

test('the settings field works on a phone: boxes the size of a thumb, nothing wider than the screen', async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  await newCampaign(owner.api, library.id, 'Zorro');

  const session = await signedInPage(browser, owner.subject, {
    viewport: { width: 375, height: 800 },
  });
  const { page } = session;
  const card = campaignCard(await openLibrary(page, library), 'Zorro');

  await card.getByRole('button', { name: 'Edit', exact: true }).click();
  const title = card.locator('[data-campaign-form]').getByLabel('Title', { exact: true });
  const plural = card.locator('[data-campaign-form]').getByLabel('Plural', { exact: true });
  await title.scrollIntoViewIfNeeded();
  await expect(title).toBeVisible();
  await expect(plural).toBeVisible();

  for (const box of [title, plural]) {
    const size = await box.boundingBox();
    expect(size?.height ?? 0).toBeGreaterThanOrEqual(44);
    expect((size?.x ?? 0) + (size?.width ?? 0)).toBeLessThanOrEqual(375);
  }

  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  await session.context.close();
});

test("a campaign's GM with no library membership edits it and names their game master; a player cannot", async ({
  browser,
}) => {
  const owner = await newUser('owner', ['tenant_creator']);
  const library = await newLibrary(owner.api);
  const campaign = await newCampaign(owner.api, library.id, 'Zorro');
  const gm = await newUser('gm');
  const player = await newUser('player');
  await makeGm(owner.api, library.id, campaign.id, gm.me.id);
  await addPlayer(owner.api, library.id, campaign.id, player.me.id);
  const path = { tenant_id: library.id, campaign_id: campaign.id };

  const asGm = await signedInPage(browser, gm.subject);
  const card = campaignCard(await openLibrary(asGm.page, library), 'Zorro');

  // Editing is theirs; managing the other GMs, which needs the library's roster, is not.
  await expect(card.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
  await expect(card.locator('[data-gm-management]')).toHaveCount(0);
  await card.getByRole('button', { name: 'Edit', exact: true }).click();
  const form = card.locator('[data-campaign-form]');
  await form.getByLabel('Title', { exact: true }).fill('Storyteller');
  await form.getByLabel('Plural', { exact: true }).fill('Storytellers');
  await card.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(card.locator('[data-campaign-meta]')).toContainText('test · Storyteller');
  await expect(card.getByRole('button', { name: 'Step down as Storyteller' })).toBeVisible();
  const saved = await ok(
    owner.api.GET('/tenants/{tenant_id}/campaigns/{campaign_id}', { params: { path } }),
  );
  expect([saved.gm_title, saved.gm_title_plural]).toEqual(['Storyteller', 'Storytellers']);
  await asGm.context.close();

  // A player of the same campaign has no Edit.
  const asPlayer = await signedInPage(browser, player.subject);
  const seen = campaignCard(await openLibrary(asPlayer.page, library), 'Zorro');
  await expect(seen.locator('[data-campaign-meta]')).toBeVisible();
  await expect(seen.getByRole('button', { name: 'Edit', exact: true })).toHaveCount(0);
  await asPlayer.context.close();
});
