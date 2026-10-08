import { type Browser, type BrowserContext, expect, type Page } from '@playwright/test';
import { type Api, apiAs, ok } from '../../../inventory-web/tests/e2e/support/api';
import { AUTHGEAR_URL, SUBJECT_COOKIE } from '../../../inventory-web/tests/e2e/support/env';

/** Logs `page` in as `subject` through the fake Authgear's real PKCE round trip (ADR 0114). */
export async function signIn(page: Page, context: BrowserContext, subject: string): Promise<void> {
  await context.addCookies([{ name: SUBJECT_COOKIE, value: subject, url: AUTHGEAR_URL }]);
  await page.goto('/');
  // The header's button: the home page has a second one, and the header is on every page.
  await page.getByRole('banner').getByRole('button', { name: 'Log in' }).click();
  await expect(page.locator('[data-account-signed-in]')).toBeVisible();
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

/** Publishes a release of a repository, acknowledging whatever it breaks: a test world wants it out. */
export async function publish(api: Api, repositoryId: string) {
  await ok(
    api.PUT('/tenants/{tenant_id}/published', {
      params: { path: { tenant_id: repositoryId } },
      body: { breaking: false, acknowledge_breaking: true },
    }),
  );
}

/** Invites a library to a repository. */
export async function invite(api: Api, repositoryId: string, libraryId: string) {
  await ok(
    api.PUT('/tenants/{tenant_id}/subscribers/{subscriber_tenant_id}', {
      params: { path: { tenant_id: repositoryId, subscriber_tenant_id: libraryId } },
    }),
  );
}

/** A catalog item, with a link name where one is given. */
export async function addItem(api: Api, tenantId: string, name: string, slug?: string) {
  return ok(
    api.POST('/tenants/{tenant_id}/items', {
      params: { path: { tenant_id: tenantId } },
      body: { name, prototype_ids: [], in_public_catalog: false, ...(slug ? { slug } : {}) },
    }),
  );
}

/** A stat group, and the stats (whole numbers) in it. */
export async function addStatGroup(api: Api, tenantId: string, name: string, stats: string[] = []) {
  const group = await ok(
    api.POST('/tenants/{tenant_id}/stat-groups', {
      params: { path: { tenant_id: tenantId } },
      body: { name, priority: 0, mandatory: false },
    }),
  );

  for (const stat of stats) {
    await ok(
      api.POST('/tenants/{tenant_id}/stat-definitions', {
        params: { path: { tenant_id: tenantId } },
        body: { name: stat, stat_group_id: group.id, value_type: 'int' },
      }),
    );
  }

  return group;
}

/** How many items, and how many stat groups, a tenant holds. */
export async function holdings(api: Api, tenantId: string) {
  const items = await ok(
    api.GET('/tenants/{tenant_id}/items', { params: { path: { tenant_id: tenantId } } }),
  );
  const groups = await ok(
    api.GET('/tenants/{tenant_id}/stat-groups', { params: { path: { tenant_id: tenantId } } }),
  );

  return { items: items.total, statGroups: groups.total };
}
