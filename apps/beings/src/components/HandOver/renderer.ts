// Handing a being to a player (ADR 0272), the capability account-hub's /beings page has (RFC 0014),
// on the same routes: pick one of the campaigns the viewer GMs, then one of its players. The roster
// names come back where the viewer may read them (ADR 0176); who may hand over is the API's.

import { errorMessage } from '../../lib/errorMessage';
import { handOver, listCampaignPlayers, playerName } from '../../lib/people';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { CampaignSummary } from '../../lib/types';

const required = requiredIn('Hand over');

export type HandOverOptions = {
  root: HTMLElement;
  tenantId: string;
  // The campaigns the viewer GMs in this library.
  campaigns: readonly CampaignSummary[];
  // After a hand over went through.
  onDone: () => void;
};

export type RenderedHandOver = {
  load(entityId: string): void;
};

export function renderHandOver(options: HandOverOptions): RenderedHandOver {
  const { root, tenantId, campaigns } = options;
  const select = required<HTMLSelectElement>(root, '[data-campaign]');
  const status = required<HTMLElement>(root, '[data-status]');
  const players = required<HTMLUListElement>(root, '[data-players]');
  const template = required<HTMLTemplateElement>(root, '[data-player-template]');

  select.append(
    new Option('Choose a campaign…', ''),
    ...campaigns.map((campaign) => new Option(campaign.name, campaign.id)),
  );

  let entityId: string | null = null;
  // Only the newest answer paints, if the campaign was changed meanwhile.
  let latest = 0;

  async function use(playerId: string) {
    if (!entityId) return;

    say(status, 'Handing over…');
    players.querySelectorAll('button').forEach((button) => {
      button.disabled = true;
    });

    try {
      await handOver(tenantId, entityId, playerId);
      say(status, 'Handed over.');
      options.onDone();
    } catch (error) {
      say(status, errorMessage(error), true);
      players.querySelectorAll('button').forEach((button) => {
        button.disabled = false;
      });
    }
  }

  select.addEventListener('change', async () => {
    const turn = ++latest;

    players.hidden = true;
    players.replaceChildren();

    if (!select.value) {
      say(status, '');
      return;
    }

    say(status, 'Loading players…');

    try {
      const roster = await listCampaignPlayers(tenantId, select.value);

      if (turn !== latest) return;

      players.replaceChildren(
        ...roster.map((player) => {
          const row = cloneTemplate<HTMLLIElement>(template, 'li');

          required<HTMLElement>(row, '[data-name]').textContent = playerName(player);
          required<HTMLButtonElement>(row, '[data-use]').addEventListener(
            'click',
            () => void use(player.id),
          );

          return row;
        }),
      );
      players.hidden = roster.length === 0;
      say(status, roster.length === 0 ? 'This campaign has no players yet.' : '');
    } catch (error) {
      if (turn === latest) say(status, errorMessage(error), true);
    }
  });

  return {
    load(id) {
      entityId = id;
      root.hidden = false;
    },
  };
}
