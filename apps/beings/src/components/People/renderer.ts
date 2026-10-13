// Who plays a being (ADR 0271): its owner first, then the players who share it, each with the
// campaign they play it in, named where the viewer may read the names (ADR 0176).

import { errorMessage } from '../../lib/errorMessage';
import { whoPlays } from '../../lib/people';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { Character } from '../../lib/types';

const required = requiredIn('People');

export type RenderedPeople = {
  /** Shows the people of `character`, or that nobody plays a being that has no character row. */
  load(tenantId: string, character: Character | null): Promise<void>;
};

// `root` is the <People /> block.
export function renderPeople(root: HTMLElement): RenderedPeople {
  const none = required<HTMLElement>(root, '[data-none]');
  const list = required<HTMLUListElement>(root, '[data-list]');
  const template = required<HTMLTemplateElement>(root, '[data-person-template]');

  return {
    async load(tenantId, character) {
      root.hidden = false;
      list.hidden = true;
      list.replaceChildren();

      if (!character || character.players.length === 0) {
        say(none, 'Nobody plays this being. It is an NPC.');
        return;
      }

      say(none, '');

      try {
        const people = await whoPlays(tenantId, character);

        list.replaceChildren(
          ...people.map((person) => {
            const row = cloneTemplate<HTMLLIElement>(template, 'li');
            const campaign = required<HTMLElement>(row, '[data-campaign]');

            required<HTMLElement>(row, '[data-name]').textContent = person.name;
            required<HTMLElement>(row, '[data-owner]').hidden = !person.owner;
            required<HTMLElement>(row, '[data-you]').hidden = !person.you;
            campaign.hidden = !person.campaign;
            campaign.textContent = person.campaign ? `in ${person.campaign}` : '';

            return row;
          }),
        );
        list.hidden = false;
      } catch (error) {
        say(none, `Couldn't load the players: ${errorMessage(error)}`, true);
      }
    },
  };
}
