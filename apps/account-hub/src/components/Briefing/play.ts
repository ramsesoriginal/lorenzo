import { askFirst } from '../../lib/askFirst';
import type { TableCard } from '../../lib/campaigns';
import { sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { tenantHref } from '../../lib/tenantKind';
import { leaveCampaign } from '../../lib/tenants';

const required = requiredIn('Briefing');

/** One seat of the person's: the campaign card to leave it by, and the player id that is the seat. */
export type PlaySeat = { card: TableCard; playerId: string };

// One line for each campaign the person plays in: its name, the library and who they play, a way
// into it and a way to leave. The block is there only when they play somewhere.
export function showPlay(root: HTMLElement, seats: PlaySeat[], onLeft: () => void): void {
  const section = required<HTMLElement>(root, '[data-play]');
  const error = required<HTMLElement>(section, '[data-error]');

  required<HTMLElement>(section, '[data-play-list]').replaceChildren(
    ...seats.map(({ card, playerId }) => {
      const fragment = fromTemplate(root, '[data-play-template]');
      const link = required<HTMLAnchorElement>(fragment, '[data-link]');
      const characters =
        card.characters === null
          ? ''
          : card.characters.length > 0
            ? `You play ${card.characters.join(', ')}`
            : 'No character yet';

      required<HTMLElement>(fragment, '[data-name]').textContent = card.name;
      required<HTMLElement>(fragment, '[data-meta]').textContent = [card.libraryName, characters]
        .filter(Boolean)
        .join(' · ');
      link.href = tenantHref(card.librarySlug);

      required<HTMLButtonElement>(fragment, '[data-leave]').addEventListener(
        'click',
        async (event) => {
          const button = event.currentTarget as HTMLButtonElement;
          const confirmed = await askFirst(
            `Leave "${card.name}"? This removes every character link this grants you here - it can't be undone from this page.`,
            { confirm: 'Leave the campaign', cancel: 'Stay' },
          );

          if (!confirmed) return;

          button.disabled = true;

          try {
            await leaveCampaign(card.tenantId, card.campaignId, playerId);
            onLeft();
          } catch (cause) {
            button.disabled = false;
            sayError(error, cause);
          }
        },
      );

      return rootElement(fragment);
    }),
  );
  section.hidden = seats.length === 0;
}
