// Your seat in one campaign, on /campaigns's "Where you play" (ADR 0179): your characters there and
// the actions that belong to a seat. Moved unchanged from the /characters page it replaces: rename
// a character, create one, use one of your characters from another campaign of the library
// (RFC 0014), stop using a linked one (ADR 0170), leave the campaign (RFC 0017 (c)).

import { createCharacter, linkCharacterToPlayer, updateCharacter } from '../../lib/characters';
import { reusableCharactersFor } from '../../lib/format';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { leaveCampaign } from '../../lib/tenants';
import type {
  CampaignSummaryOut,
  CharacterSummaryOut,
  MeOut,
  PlayerContextOut,
} from '../../lib/types';
import { bindUnlinkCharacter } from '../../lib/unlinkCharacter';

const required = requiredIn('Seat');

export type SeatInput = {
  campaign: CampaignSummaryOut;
  libraryName: string;
  player: PlayerContextOut;
  me: MeOut;
  // Who owns each of the seat's characters, if it could be read (loadSeatOwners).
  owners: Map<string, string | null>;
  onChanged: () => void;
};

// One character of the seat: its name, Rename (in place), and "Stop using here" where that applies.
function renderCharacter(
  root: HTMLElement,
  character: CharacterSummaryOut,
  input: SeatInput,
): HTMLElement {
  const { campaign, player, owners, onChanged } = input;
  const fragment = fromTemplate(root, '[data-character-template]');
  const name = required<HTMLElement>(fragment, '[data-character-name]');
  const renameButton = required<HTMLButtonElement>(fragment, '[data-rename]');
  const unlinkButton = required<HTMLButtonElement>(fragment, '[data-unlink]');
  const form = required<HTMLFormElement>(fragment, '[data-rename-form]');
  const nameInput = required<HTMLInputElement>(fragment, '[data-rename-input]');
  const cancelButton = required<HTMLButtonElement>(fragment, '[data-rename-cancel]');
  const status = required<HTMLElement>(fragment, '[data-status]');

  name.textContent = character.name;

  // "Stop using here" is the reverse of reusing a character from another
  // campaign (ADR 0170), so it is only offered for a link that isn't the
  // character's own owner's: control comes from the links, and an owner
  // who unlinked themselves would lose their character. An owner that
  // couldn't be read leaves the button out.
  const owner = owners.get(character.entity_id);

  if (owner !== undefined && owner !== player.id) {
    unlinkButton.hidden = false;
    bindUnlinkCharacter(
      unlinkButton,
      status,
      {
        tenantId: player.tenant_id,
        characterId: character.entity_id,
        characterName: character.name,
        playerId: player.id,
        campaignName: campaign.name,
      },
      onChanged,
    );
  }

  // The name, or its edit form: one at a time.
  function showName() {
    form.hidden = true;
    name.hidden = false;
    renameButton.hidden = false;
    unlinkButton.hidden = !(owner !== undefined && owner !== player.id);
  }

  renameButton.addEventListener('click', () => {
    nameInput.value = character.name;
    name.hidden = true;
    renameButton.hidden = true;
    unlinkButton.hidden = true;
    form.hidden = false;
    nameInput.focus();
  });
  cancelButton.addEventListener('click', showName);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const newName = nameInput.value.trim();

    if (newName === '' || newName === character.name) {
      showName();

      return;
    }

    say(status, 'Saving…');

    try {
      await updateCharacter(player.tenant_id, character.entity_id, { name: newName });
      onChanged();
    } catch (e) {
      sayError(status, e);
    }
  });

  return rootElement(fragment);
}

// `root` is the <Seat /> block.
export function renderSeat(root: HTMLElement, input: SeatInput): void {
  const { campaign, libraryName, player, me, onChanged } = input;

  required<HTMLElement>(root, '[data-name]').textContent = campaign.name;
  required<HTMLElement>(root, '[data-where]').textContent = ` in ${libraryName}`;

  const characters = required<HTMLElement>(root, '[data-characters]');
  const noCharacters = required<HTMLElement>(root, '[data-no-characters]');

  noCharacters.hidden = player.characters.length > 0;
  characters.hidden = player.characters.length === 0;
  characters.replaceChildren(
    ...player.characters.map((character) => renderCharacter(root, character, input)),
  );

  const createForm = required<HTMLFormElement>(root, '[data-create-form]');
  const createName = required<HTMLInputElement>(root, '[data-create-name]');
  const createStatus = required<HTMLElement>(root, '[data-create-status]');

  createForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const name = createName.value.trim();

    if (name === '') return;

    say(createStatus, 'Creating…');

    try {
      await createCharacter(player.tenant_id, {
        name,
        owner_player_id: player.id,
        player_ids: [],
      });
      onChanged();
      createName.value = '';
      say(createStatus, '');
    } catch (e) {
      sayError(createStatus, e);
    }
  });

  // Only before there is a character here.
  if (player.characters.length === 0) {
    const reusable = reusableCharactersFor(me, player.tenant_id, campaign.id);

    if (reusable.length > 0) {
      required<HTMLElement>(root, '[data-reuse]').hidden = false;
      required<HTMLElement>(root, '[data-reusable]').replaceChildren(
        ...reusable.map((character) => {
          const fragment = fromTemplate(root, '[data-reusable-template]');
          const status = required<HTMLElement>(fragment, '[data-status]');

          required<HTMLElement>(fragment, '[data-reusable-name]').textContent = character.name;
          required<HTMLButtonElement>(fragment, '[data-use]').addEventListener(
            'click',
            async () => {
              say(status, 'Linking…');

              try {
                await linkCharacterToPlayer(player.tenant_id, character.entity_id, player.id);
                onChanged();
              } catch (e) {
                sayError(status, e);
              }
            },
          );

          return rootElement(fragment);
        }),
      );
    }
  }

  const leaveButton = required<HTMLButtonElement>(root, '[data-leave]');
  const leaveStatus = required<HTMLElement>(root, '[data-leave-status]');

  leaveButton.addEventListener('click', async () => {
    const confirmed = window.confirm(
      `Leave "${campaign.name}"? This removes every character link this grants you here - it can't be undone from this page.`,
    );

    if (!confirmed) return;

    say(leaveStatus, 'Leaving…');

    try {
      await leaveCampaign(player.tenant_id, campaign.id, player.id);
      onChanged();
    } catch (e) {
      sayError(leaveStatus, e);
    }
  });
}
