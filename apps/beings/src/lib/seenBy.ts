// Who sees a being (BN6, ADR 0529): everyone who can read the library, or only the game masters
// (and whoever plays it), or a few named people the page does not edit. The API says it with the
// being's outer audience; this is how the page reads and writes that.

import type { components } from './api';
import type { GmWords } from './gmTitle';

export type Audience = components['schemas']['InformationAudience'];
export type Who = 'everyone' | 'gm' | 'named';

/** Which of the three an audience is. */
export function whoOf(audience: Audience): Who {
  if (audience.is_public) return 'everyone';

  const named = (audience.entity_ids?.length ?? 0) + (audience.player_ids?.length ?? 0);

  return named > 0 ? 'named' : 'gm';
}

/** The audience that says `who`; "named" is only ever kept as it was, never made here. */
export function audienceFor(who: Who, current: Audience): Audience {
  if (who === 'everyone') return { is_public: true, entity_ids: [], player_ids: [] };
  if (who === 'gm') return { is_public: false, entity_ids: [], player_ids: [] };

  return current;
}

/** What each choice is called, with the game masters named as the campaign names them. */
export function whoText(who: Who, words: GmWords): { label: string; hint: string } {
  switch (who) {
    case 'everyone':
      return { label: 'Everyone', hint: 'Anyone who can read this library sees this being.' };
    case 'gm':
      return {
        label: `${words.plural} only`,
        hint: `Only ${words.plural} and whoever plays it see this being.`,
      };
    case 'named':
      return { label: 'Some people', hint: 'Only the people it was shared with see this being.' };
  }
}
