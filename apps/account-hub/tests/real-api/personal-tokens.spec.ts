// Connecting a device and personal access tokens (ADR 0268, 0269): the device asks for a code, a
// signed-in person approves or denies it on /device, and the token it gets works until revoked
// in the profile's list.
import { expect, type Page, test } from '@playwright/test';
import { ok } from '../../../inventory-web/tests/e2e/support/api';
import { API_URL } from '../../../inventory-web/tests/e2e/support/env';
import { newUser, signedInPage } from './support';

type Flow = { device_code: string; user_code: string; verification_uri: string };

// What a device does first, with no login at all.
async function startDevice(clientName = 'lorenzo CLI on test laptop'): Promise<Flow> {
  const response = await fetch(`${API_URL}/device-codes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_name: clientName }),
  });
  expect(response.status).toBe(201);
  return (await response.json()) as Flow;
}

async function poll(flow: Flow) {
  return fetch(`${API_URL}/device-codes/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_code: flow.device_code }),
  });
}

const asBearer = (secret: string) =>
  fetch(`${API_URL}/me`, { headers: { Authorization: `Bearer ${secret}` } });

async function openDevice(page: Page, query: string) {
  await page.goto(`/device${query}`);
  await expect(page.locator('#loading')).toBeHidden();
}

test('a person approves the code in the address, names the token, and the device gets it', async ({
  browser,
}) => {
  const person = await newUser('pat');
  const flow = await startDevice();
  const session = await signedInPage(browser, person.subject);
  const { page } = session;

  await openDevice(page, `?code=${flow.user_code}`);
  await expect(page.getByText('lorenzo CLI on test laptop')).toBeVisible();
  await expect(page.getByLabel('Name this token')).toHaveValue('lorenzo CLI on test laptop');
  // No expiry unless one is chosen.
  await expect(page.getByLabel('It stops working')).toHaveValue('never');

  await page.getByLabel('Name this token').fill('Test laptop');
  await page.getByLabel('It stops working').selectOption({ label: 'In 30 days' });
  const waiting = await poll(flow);
  expect(waiting.status).toBe(400);
  expect(((await waiting.json()) as { type: string }).type).toContain('authorization-pending');

  await page.getByRole('button', { name: 'Connect this device' }).click();
  await expect(page.getByText('Connected. You can go back to your device')).toBeVisible();

  // Polling again at once is told to slow down; after the interval the token is handed over.
  expect(((await (await poll(flow)).json()) as { type: string }).type).toContain('slow-down');
  await page.waitForTimeout(5_200);
  const issued = (await (await poll(flow)).json()) as {
    access_token: string;
    id: string;
    name: string;
    expires_at: string | null;
  };
  expect(issued.access_token).toMatch(/^lor_pat_/);
  expect(issued.name).toBe('Test laptop');
  const inThirtyDays = Date.now() + 30 * 24 * 60 * 60 * 1000;
  expect(Math.abs(new Date(issued.expires_at ?? 0).getTime() - inThirtyDays)).toBeLessThan(120_000);
  expect((await asBearer(issued.access_token)).status).toBe(200);

  // The profile lists it, never its secret, and revoking asks first and ends it.
  await page.goto('/profile');
  const row = page
    .locator('[data-personal-tokens] [data-list] > li')
    .filter({ hasText: 'Test laptop' });
  await expect(row).toContainText('Last used');
  await expect(row).toContainText('Expires');
  await expect(page.locator('[data-personal-tokens]')).not.toContainText(issued.access_token);

  await row.getByRole('button', { name: 'Revoke' }).click();
  await expect(page.locator('[data-personal-tokens] [data-list] > li')).toHaveCount(0);
  expect(session.confirmations.some((message) => message.includes('"Test laptop"'))).toBe(true);
  expect((await asBearer(issued.access_token)).status).toBe(401);
  expect(await ok(person.api.GET('/me/tokens'))).toEqual([]);
  await session.context.close();
});

test('a code can be typed, and a wrong or used one is said in words', async ({ browser }) => {
  const person = await newUser('pat-typed');
  const flow = await startDevice();
  const session = await signedInPage(browser, person.subject);
  const { page } = session;

  await openDevice(page, '');
  await page.getByLabel('Code from your device').fill('not a code');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByText('A code is eight letters')).toBeVisible();

  await page.getByLabel('Code from your device').fill('BCDF-GHJK');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByText("That code isn't waiting for approval")).toBeVisible();

  await page
    .getByLabel('Code from your device')
    .fill(flow.user_code.toLowerCase().replace('-', ' '));
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('button', { name: 'Connect this device' })).toBeVisible();
  await session.context.close();
});

test('denying the code gives the device nothing', async ({ browser }) => {
  const person = await newUser('pat-deny');
  const flow = await startDevice();
  const session = await signedInPage(browser, person.subject);
  const { page } = session;

  await openDevice(page, `?code=${flow.user_code}`);
  await page.getByRole('button', { name: 'Deny' }).click();
  await expect(page.getByText('Denied. Nothing was connected.')).toBeVisible();

  const answer = await poll(flow);
  expect(answer.status).toBe(400);
  expect(((await answer.json()) as { type: string }).type).toContain('access-denied');
  expect(await ok(person.api.GET('/me/tokens'))).toEqual([]);
  await session.context.close();
});
