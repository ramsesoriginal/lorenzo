import { expect, test } from '@playwright/test';

test('without sign-in configured the page says it is sample data', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#titlebar')).toContainText('Sample data');
  await expect(page.getByRole('button', { name: 'Sign in' })).toHaveCount(0);
});

test.describe('with sign-in configured', () => {
  test.use({ baseURL: 'http://localhost:4332' });

  test.beforeEach(async ({ page }) => {
    await page.route('http://authgear.test/.well-known/openid-configuration', (route) =>
      route.fulfill({
        json: {
          issuer: 'http://authgear.test',
          authorization_endpoint: 'http://authgear.test/oauth2/authorize',
          token_endpoint: 'http://authgear.test/oauth2/token',
          userinfo_endpoint: 'http://authgear.test/oauth2/userinfo',
          revocation_endpoint: 'http://authgear.test/oauth2/revoke',
          end_session_endpoint: 'http://authgear.test/oauth2/end_session',
          jwks_uri: 'http://authgear.test/oauth2/jwks',
        },
      }),
    );
    await page.route('http://authgear.test/oauth2/authorize**', (route) =>
      route.fulfill({ contentType: 'text/html', body: 'authgear' }),
    );
  });

  test('the workbench and its shortcuts work before sign-in has finished loading', async ({
    page,
  }) => {
    // The sign-in code arrives slowly; the page must not wait for it before it can be used.
    await page.route('**/_astro/auth.*.js', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 3000));
      await route.continue();
    });
    await page.goto('/');
    await page.keyboard.press('Control+k');
    await expect(page.getByLabel('Command palette')).toBeVisible();
    await expect(page.locator('#titlebar')).not.toContainText('Not signed in');
    await expect(page.locator('[data-tab="explorer"]')).toBeVisible();
  });

  test('a signed-out visitor is offered Sign in', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#titlebar')).toContainText('Not signed in');
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
    // the workbench is still there to look at
    await expect(page.locator('[data-tab="entry"]')).toBeVisible();
  });

  test('Sign in goes to Authgear with this client and the slash-form redirect', async ({
    page,
  }) => {
    await page.goto('/');
    const request = page.waitForRequest('http://authgear.test/oauth2/authorize**');
    await page.getByRole('button', { name: 'Sign in' }).click();
    const url = new URL((await request).url());
    expect(url.searchParams.get('client_id')).toBe('bench-test-client');
    expect(url.searchParams.get('redirect_uri')).toBe('http://localhost:4332/auth/redirect/');
    expect(url.searchParams.get('code_challenge_method')).toBe('S256');
    expect(url.searchParams.get('response_type')).toBe('code');
  });
});
