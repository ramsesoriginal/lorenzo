// "Unlink" on a character: undo a roster link (ADR 0170), the reverse of ADR 0079's reuse. It never
// unlinks a character's owner: control comes from the roster links, so that would leave a
// character owned by someone who no longer controls it. The owner is read when the button is
// pressed, whatever the page knew when it drew it.
//
// Two places have one: a campaign's roster, where a manager does it for a player, and a player's own
// seat, where they stop using a character of another campaign.

import { ownerLinkRefusal, unlinkCharacterConfirmation } from './adminCopy';
import { getCharacter, unlinkCharacterFromPlayer } from './characters';
import { say, sayError } from './statusLine';

export interface UnlinkTarget {
  tenantId: string;
  characterId: string;
  characterName: string;
  playerId: string;
  campaignName: string;
  // The player's name when someone else is doing it ("Pia's seat"); omitted when it is the
  // player's own.
  playerName?: string;
}

// Binds `button`. `status` is where it says how it went. A button for someone else's seat is
// named for its character, since it may only be an icon; a player's own has its words.
export function bindUnlinkCharacter(
  button: HTMLButtonElement,
  status: HTMLElement,
  target: UnlinkTarget,
  onDone: () => void,
): void {
  if (target.playerName !== undefined) {
    button.setAttribute('aria-label', `Unlink ${target.characterName}`);
    button.title = `Unlink ${target.characterName}`;
  }

  button.addEventListener('click', async () => {
    if (
      !window.confirm(
        unlinkCharacterConfirmation(target.characterName, target.campaignName, target.playerName),
      )
    ) {
      return;
    }

    button.disabled = true;
    say(status, 'Unlinking…');

    try {
      // Read now: an owner can change in between, and the cost of a stale answer is a character
      // its owner no longer controls.
      const character = await getCharacter(target.tenantId, target.characterId);

      if (character.owner_player_id === target.playerId) {
        button.disabled = false;
        say(status, ownerLinkRefusal(target.characterName, target.playerName));

        return;
      }

      await unlinkCharacterFromPlayer(target.tenantId, target.characterId, target.playerId);
      onDone();
    } catch (e) {
      button.disabled = false;
      sayError(status, e);
    }
  });
}
