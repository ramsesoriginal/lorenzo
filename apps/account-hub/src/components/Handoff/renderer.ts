// RFC 0014's GM-handoff sub-slice: hand a being to a player as a real, lasting character -
// roster-link, then set owner_player_id, in that order (see ADR 0079's partial-failure reasoning: a
// linked-but-not-yet-owned being is recoverable, the reverse isn't).

import { linkCharacterToPlayer, updateCharacter } from '../../lib/characters';
import { resolveDisplayName } from '../../lib/format';
import { say, sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import { invitePlayer, listCampaignPlayers, listTenantRoster } from '../../lib/tenants';
import type { BeingSummaryOut, CampaignSummaryOut } from '../../lib/types';
import { renderUserPicker } from '../UserPicker/renderer';

const required = requiredIn('Handoff');

export type HandoffInput = {
  being: BeingSummaryOut;
  tenantId: string;
  // The campaigns the caller GMs in this library: a hand-off needs one as its context.
  gmCampaigns: CampaignSummaryOut[];
  canReadRoster: boolean;
  onDone: () => void;
};

// `root` is the <Handoff /> block.
export function renderHandoff(root: HTMLElement, input: HandoffInput): void {
  const { being, tenantId, gmCampaigns, canReadRoster, onDone } = input;
  const select = required<HTMLSelectElement>(root, '[data-campaign]');
  const status = required<HTMLElement>(root, '[data-handoff-status]');
  const players = required<HTMLElement>(root, '[data-players]');
  const playerList = required<HTMLElement>(root, '[data-player-list]');

  select.append(
    new Option('Choose a campaign…', ''),
    ...gmCampaigns.map((campaign) => new Option(campaign.name, campaign.id)),
  );

  async function handOffTo(playerId: string): Promise<void> {
    say(status, 'Handing off…');

    try {
      await linkCharacterToPlayer(tenantId, being.entity_id, playerId);
      await updateCharacter(tenantId, being.entity_id, { owner_player_id: playerId });
      onDone();
    } catch (e) {
      sayError(status, e);
    }
  }

  // Inviting someone new is the same as picking a player, once they are one.
  renderUserPicker(required<HTMLElement>(root, '[data-user-picker]'), async (user) => {
    try {
      const newPlayer = await invitePlayer(tenantId, select.value, { user_id: user.id });

      await handOffTo(newPlayer.id);
    } catch (e) {
      sayError(status, e);
    }
  });

  // Only the newest answer paints, if the campaign was changed meanwhile.
  let latest = 0;

  select.addEventListener('change', async () => {
    const turn = ++latest;
    const campaignId = select.value;

    players.hidden = true;
    playerList.replaceChildren();

    if (campaignId === '') {
      say(status, '');

      return;
    }

    say(status, 'Loading players…');

    try {
      // The roster is a library admins' read: a campaign GM with no membership gets a 404 for it,
      // and that is a normal GM (ADR 0035). Without it a player is named by their user id, as
      // resolveDisplayName does for any miss.
      const [existing, roster] = await Promise.all([
        listCampaignPlayers(tenantId, campaignId),
        canReadRoster ? listTenantRoster(tenantId) : Promise.resolve(null),
      ]);

      if (turn !== latest) return;

      playerList.replaceChildren(
        ...existing.items.map((player) => {
          const row = cloneRoot(root, '[data-player-template]');

          required<HTMLElement>(row, '[data-player-name]').textContent = resolveDisplayName(
            roster?.items ?? [],
            player.user_id,
          );
          required<HTMLButtonElement>(row, '[data-use]').addEventListener(
            'click',
            () => void handOffTo(player.id),
          );

          return row;
        }),
      );
      say(status, '');
      players.hidden = false;
    } catch (e) {
      if (turn === latest) sayError(status, e);
    }
  });
}
