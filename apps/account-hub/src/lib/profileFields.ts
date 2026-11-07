// One profile field at a time (ADR 0418, PT2): each saves as it is changed, so what is sent is the one
// field that changed, and what Undo sends is what it held before. Pure, so it is tested without a
// browser.

import { localesToText, normalizeLocales, textOrNull } from './format';
import type { MeOut, ProfileUpdate } from './types';

export type ProfileField =
  | 'nickname'
  | 'display_name'
  | 'pronouns'
  | 'bio'
  | 'locales'
  | 'user_color';

export const FIELD_LABEL: Record<ProfileField, string> = {
  nickname: 'Nickname',
  display_name: 'Display name',
  pronouns: 'Pronouns',
  bio: 'Bio',
  locales: 'Languages',
  user_color: 'Colour',
};

/** What a field holds, as it is typed: an empty string is none. */
export function typedValue(me: MeOut, field: ProfileField): string {
  if (field === 'locales') return localesToText(me.locales);

  return me[field] ?? '';
}

/** The PATCH for one field, from what was typed; null when it is what the profile already holds. */
export function fieldPatch(me: MeOut, field: ProfileField, typed: string): ProfileUpdate | null {
  if (field === 'locales') {
    const locales = normalizeLocales(typed);

    return JSON.stringify(locales) === JSON.stringify(me.locales) ? null : { locales };
  }

  const value = textOrNull(typed);

  return value === (me[field] ?? null) ? null : ({ [field]: value } as ProfileUpdate);
}
