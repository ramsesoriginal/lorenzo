import type { LorenzoClient } from './index';

/**
 * A person's appearance in their account (ADR 0532): what the web shell asks for, as the two calls
 * it needs. `load` gives the account's own words, `save` replaces them.
 */
export function accountPreferences(client: LorenzoClient) {
  return {
    async load(): Promise<unknown> {
      const got = await client.GET('/me/preferences');

      return got.data ?? null;
    },
    async save(prefs: { theme?: string; density?: string; motion?: string }): Promise<void> {
      await client.PUT('/me/preferences', { body: prefs as never });
    },
  };
}
