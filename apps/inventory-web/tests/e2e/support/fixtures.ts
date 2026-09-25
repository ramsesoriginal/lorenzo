// The tests' fixtures (ADR 0114): a fresh world, and browser pages logged in as its people
// through the app's own login button and the fake Authgear.
import { type BrowserContext, test as base, expect, type Page } from '@playwright/test';
import { AUTHGEAR_URL, SUBJECT_COOKIE } from './env.ts';
import { buildWorld, type Person, type World } from './world.ts';

type Fixtures = {
  world: World;
  /** A new browser, logged in as `person`, on the home page. */
  as: (person: Person) => Promise<Page>;
};

export const test = base.extend<Fixtures>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright's fixture signature.
  world: async ({}, use) => {
    await use(await buildWorld());
  },
  as: async ({ browser }, use) => {
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
