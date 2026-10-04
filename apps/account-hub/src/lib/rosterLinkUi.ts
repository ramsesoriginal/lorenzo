// "Stop using in this campaign": undo a roster link (ADR 0170), the reverse of
// ADR 0079's reuse. Like userPicker.ts (ADR 0074), a lib/*.ts module that
// builds DOM. It never unlinks a character's owner: control comes from the
// roster links, so that would leave a character owned by someone who no longer
// controls it. A page that already knows the owner doesn't build the button;
// otherwise the owner is read when it is pressed.
import { ownerLinkRefusal, unlinkCharacterConfirmation } from './adminCopy';
import { getCharacter, unlinkCharacterFromPlayer } from './characters';
import { createStatusSpan } from './dom';
import { showError } from './errorUi';

export interface UnlinkTarget {
  tenantId: string;
  characterId: string;
  characterName: string;
  playerId: string;
  campaignName: string;
  // The player's name when someone else is doing it ("Pia's seat"); omitted
  // when it is the player's own.
  playerName?: string;
}

export function renderUnlinkCharacter(target: UnlinkTarget, onDone: () => void): HTMLElement {
  const container = document.createElement('span');
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = target.playerName === undefined ? 'Stop using in this campaign' : 'Unlink';
  const status = createStatusSpan();
  container.append(button, status);
  button.addEventListener('click', async () => {
    if (
      !window.confirm(
        unlinkCharacterConfirmation(target.characterName, target.campaignName, target.playerName),
      )
    ) {
      return;
    }
    button.disabled = true;
    status.textContent = 'Unlinking…';
    try {
      // Read now, whatever the page knew when it drew the button: an owner
      // can change in between, and the cost of a stale answer is a character
      // its owner no longer controls.
      const character = await getCharacter(target.tenantId, target.characterId);
      if (character.owner_player_id === target.playerId) {
        button.disabled = false;
        status.textContent = ownerLinkRefusal(target.characterName, target.playerName);
        return;
      }
      await unlinkCharacterFromPlayer(target.tenantId, target.characterId, target.playerId);
      onDone();
    } catch (e) {
      button.disabled = false;
      showError(status, e);
    }
  });
  return container;
}
