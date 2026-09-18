import { apiDelete, apiFetch, apiPatch, apiUpload } from './api';
import type { MeOut, ProfileUpdate } from './types';

export async function getProfile(): Promise<MeOut> {
  return apiFetch<MeOut>('/me');
}

export async function updateProfile(patch: ProfileUpdate): Promise<MeOut> {
  return apiPatch<MeOut>('/me', patch);
}

export async function uploadProfilePicture(file: File): Promise<void> {
  await apiUpload<void>('/me/picture', 'file', file);
}

export async function deleteProfilePicture(): Promise<void> {
  await apiDelete<void>('/me/picture');
}
