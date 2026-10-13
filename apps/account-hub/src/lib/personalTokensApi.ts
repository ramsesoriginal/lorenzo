// The calls behind connecting a device and the list of personal access tokens (ADR 0269).
import { client, unwrap } from './api';
import type { DeviceApproval, DeviceCodePreviewOut, PersonalTokenOut } from './types';

export async function previewDeviceCode(code: string): Promise<DeviceCodePreviewOut> {
  return unwrap(
    await client.GET('/me/device-codes/{user_code}', { params: { path: { user_code: code } } }),
  );
}

export async function approveDeviceCode(code: string, body: DeviceApproval): Promise<void> {
  await unwrap(
    await client.POST('/me/device-codes/{user_code}/approve', {
      params: { path: { user_code: code } },
      body,
    }),
  );
}

export async function denyDeviceCode(code: string): Promise<void> {
  await unwrap(
    await client.POST('/me/device-codes/{user_code}/deny', {
      params: { path: { user_code: code } },
    }),
  );
}

export async function listPersonalTokens(): Promise<PersonalTokenOut[]> {
  return unwrap(await client.GET('/me/tokens'));
}

export async function revokePersonalToken(id: string): Promise<void> {
  await unwrap(
    await client.DELETE('/me/tokens/{token_id}', { params: { path: { token_id: id } } }),
  );
}
