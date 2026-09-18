import { apiDelete, apiPatch, apiUpload } from './api';
import type { MeOut, ProfileUpdate } from './types';

export async function updateProfile(patch: ProfileUpdate): Promise<MeOut> {
  return apiPatch<MeOut>('/me', patch);
}

export async function uploadProfilePicture(file: File): Promise<void> {
  await apiUpload<void>('/me/picture', 'file', file);
}

export async function deleteProfilePicture(): Promise<void> {
  await apiDelete<void>('/me/picture');
}
