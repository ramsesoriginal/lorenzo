import { client, pictureUpload, unwrap } from './api';
import type { MeOut, ProfileUpdate } from './types';

export async function updateProfile(patch: ProfileUpdate): Promise<MeOut> {
  return unwrap(await client.PATCH('/me', { body: patch }));
}

export async function uploadProfilePicture(file: File): Promise<void> {
  await unwrap(await client.PUT('/me/picture', { ...pictureUpload(file) }));
}

export async function deleteProfilePicture(): Promise<void> {
  await unwrap(await client.DELETE('/me/picture'));
}
