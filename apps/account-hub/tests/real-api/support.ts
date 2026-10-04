import { type Browser, type BrowserContext, expect, type Page } from '@playwright/test';
import { type Api, apiAs, ok } from '../../../inventory-web/tests/e2e/support/api';
import { AUTHGEAR_URL, SUBJECT_COOKIE } from '../../../inventory-web/tests/e2e/support/env';

/** Logs `page` in as `subject` through the fake Authgear's real PKCE round trip (ADR 0114). */
export async function signIn(page: Page, context: BrowserContext, subject: string): Promise<void> {
  await context.addCookies([{ name: SUBJECT_COOKIE, value: subject, url: AUTHGEAR_URL }]);
  await page.goto('/');
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.locator('#account-signed-in')).toBeVisible();
}

/**
 * A new browser context signed in as `subject`, answering every window.confirm with "OK" and
 * keeping what each one asked.
 */
export async function signedInPage(
  browser: Browser,
  subject: string,
  options: Parameters<Browser['newContext']>[0] = {},
) {
  const context = await browser.newContext(options);
  const page = await context.newPage();
  const confirmations: string[] = [];
  page.on('dialog', (dialog) => {
    confirmations.push(dialog.message());
    void dialog.accept();
  });
  await signIn(page, context, subject);
  return { context, page, confirmations };
}

/** A person registered with the fake Authgear and provisioned in the API. */
export async function newUser(prefix: string, roles: string[] = []) {
  const subject = `hub-${prefix}-${crypto.randomUUID()}`;
  const api = await apiAs(subject, roles);
  const me = await ok(api.GET('/me'));
  return { subject, api, me };
}

export async function newLibrary(owner: Api, name = `Library ${crypto.randomUUID()}`) {
  return ok(owner.POST('/tenants', { body: { name } }));
}

export async function newCampaign(owner: Api, tenantId: string, name: string) {
  return ok(
    owner.POST('/tenants/{tenant_id}/campaigns', {
      params: { path: { tenant_id: tenantId } },
      body: {
        name,
        slug: name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        description: '',
        game_system: 'test',
        secret: false,
      },
    }),
  );
}

/** A library's card on /tenants, found by the name its heading starts with. */
export function libraryCard(page: Page, name: string) {
  return page
    .locator('#tenant-list > li')
    .filter({ has: page.getByRole('heading', { name: new RegExp(`^${name}`) }) });
}

/** A repository's card in "Your repositories" on /tenants, found by the name its heading starts with. */
export function repositoryCard(page: Page, name: string) {
  return page
    .locator('#repository-list > li')
    .filter({ has: page.getByRole('heading', { name: new RegExp(`^${name}`) }) });
}

/** A repository, made through the API by an account holding the tenant-creator role. */
export async function newRepository(owner: Api, name = `Repository ${crypto.randomUUID()}`) {
  return ok(owner.POST('/tenants', { body: { name, kind: 'repository' } }));
}

/** A player seat for `userId` in a campaign, added by someone who manages it. */
export async function addPlayer(owner: Api, tenantId: string, campaignId: string, userId: string) {
  return ok(
    owner.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
      body: { user_id: userId },
    }),
  );
}

/** A GM grant for `userId` in a campaign, made by someone who manages it. */
export async function makeGm(owner: Api, tenantId: string, campaignId: string, userId: string) {
  return ok(
    owner.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId, user_id: userId } },
    }),
  );
}
