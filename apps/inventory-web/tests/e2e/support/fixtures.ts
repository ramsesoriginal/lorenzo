// The tests' fixtures (ADR 0114): a fresh world, and browser pages signed in as its people. Almost
// every test starts from a session the fake Authgear handed out (`as`); one goes through the
// app's own login button and the fake's PKCE round trip (`logInAs`), so that flow stays covered.
import { type BrowserContext, test as base, expect, type Page } from '@playwright/test';
import { refreshTokenFor } from './api.ts';
import { AUTHGEAR_URL, REFRESH_TOKEN_KEY, SITE_URL, SUBJECT_COOKIE } from './env.ts';
import { buildWorld, type Person, type World } from './world.ts';

type Fixtures = {
  world: World;
  /**
   * A new browser, already signed in as `person`, on no page yet: a test goes where it's going,
   * and the first page it loads is that one.
   */
  as: (person: Person) => Promise<Page>;
  /** A new browser that logs `person` in through the login button, and ends up where that lands. */
  logInAs: (person: Person) => Promise<Page>;
};

export const test = base.extend<Fixtures>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright's fixture signature.
  world: async ({}, use) => {
    await use(await buildWorld());
  },
  as: async ({ browser }, use) => {
    const contexts: BrowserContext[] = [];
    await use(async (person) => {
      const refreshToken = await refreshTokenFor(person.subject);
      const context = await browser.newContext({
        storageState: {
          cookies: [],
          origins: [
            {
              origin: new URL(SITE_URL).origin,
              localStorage: [{ name: REFRESH_TOKEN_KEY, value: refreshToken }],
            },
          ],
        },
      });
      contexts.push(context);
      return context.newPage();
    });
    await Promise.all(contexts.map((context) => context.close()));
  },
  logInAs: async ({ browser }, use) => {
    const contexts: BrowserContext[] = [];
    await use(async (person) => {
      const context = await browser.newContext();
      contexts.push(context);
      await context.addCookies([
        { name: SUBJECT_COOKIE, value: person.subject, url: AUTHGEAR_URL },
      ]);
      const page = await context.newPage();
      await page.goto('/');
      await page.getByRole('button', { name: 'Log in' }).click();
      await expect(page.getByText('Signed in as')).toBeVisible();
      return page;
    });
    await Promise.all(contexts.map((context) => context.close()));
  },
});

export { expect };
