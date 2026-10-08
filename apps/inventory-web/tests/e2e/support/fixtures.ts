// The tests' fixtures (ADR 0114): a fresh world, and browser pages signed in as its people. Almost
// every test starts from a session the fake Authgear handed out (`as`); one goes through the
// app's own login button and the fake's PKCE round trip (`logInAs`), so that flow stays covered.
//
// `test` builds a world of its own for each test. `readOnly` is for the tests that only look: they
// share one world, and one packed scene in it, per worker (ADR 0148).
import { type BrowserContext, test as base, expect, type Page } from '@playwright/test';
import { refreshTokenFor } from './api.ts';
import { AUTHGEAR_URL, REFRESH_TOKEN_KEY, SITE_URL, SUBJECT_COOKIE } from './env.ts';
import { packed } from './scenes.ts';
import { buildWorld, type Person, type World } from './world.ts';

type Browsers = {
  /**
   * A new browser, already signed in as `person`, on no page yet: a test goes where it's going,
   * and the first page it loads is that one.
   */
  as: (person: Person) => Promise<Page>;
  /** A new browser that logs `person` in through the login button, and ends up where that lands. */
  logInAs: (person: Person) => Promise<Page>;
};

const browsers = base.extend<Browsers>({
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

/** A test with a world of its own, built before it runs. */
export const test = browsers.extend<{ world: World }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright's fixture signature.
  world: async ({}, use) => {
    await use(await buildWorld());
  },
});

/** What a world's helpers do to it, which a test that shares the world must not. */
const WRITES = ['describe', 'item', 'instance', 'setStat', 'stack', 'slug', 'group'] as const;

/** `world` with the helpers that write refusing to, so a test that shares it can't change it. */
function readOnlyView(world: World): World {
  const view = { ...world };
  for (const name of WRITES) {
    view[name] = (async () => {
      throw new Error(
        `world.${name} writes, and this world is shared: that test belongs on \`test\`.`,
      );
    }) as never;
  }
  return view;
}

type Scene = Awaited<ReturnType<typeof packed>>;

/**
 * A test that only looks: it shares one world per worker, with Pia carrying `packed`'s scene in
 * it, instead of paying to build them again. What it may not do is write: no save, move, give or
 * edit in the browser, and no helper of the world that writes (those throw). A test that changes
 * anything, or counts on a world nothing else has put anything in, uses `test`.
 */
export const readOnly = browsers.extend<
  object,
  { shared: { world: World; scene: Scene }; world: World; scene: Scene }
>({
  shared: [
    // biome-ignore lint/correctness/noEmptyPattern: Playwright's fixture signature.
    async ({}, use) => {
      const world = await buildWorld();
      await use({ world, scene: await packed(world, world.pia) });
    },
    { scope: 'worker' },
  ],
  world: [async ({ shared }, use) => use(readOnlyView(shared.world)), { scope: 'worker' }],
  scene: [async ({ shared }, use) => use(shared.scene), { scope: 'worker' }],
});

export { expect };
