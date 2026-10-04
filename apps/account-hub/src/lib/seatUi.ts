// Your seat in one campaign, on /campaigns's "Where you play" (ADR 0179): your
// characters there and the actions that belong to a seat. Moved unchanged from
// the /characters page it replaces: rename a character, create one, use one of
// your characters from another campaign of the library (RFC 0014), stop using a
// linked one (ADR 0170), leave the campaign (RFC 0017 (c)). Like userPicker.ts
// (ADR 0074), a lib/*.ts module that builds DOM.
import {
  createCharacter,
  getCharacter,
  linkCharacterToPlayer,
  updateCharacter,
} from './characters';
import { createStatusSpan, renderCreateForm, renderRenameableItem } from './dom';
import { showError } from './errorUi';
import { reusableCharactersFor } from './format';
import { renderUnlinkCharacter } from './rosterLinkUi';
import { leaveCampaign } from './tenants';
import type { CampaignSummaryOut, CharacterSummaryOut, MeOut, PlayerContextOut } from './types';

// Who owns each character on the caller's seats in one library: the one fact
// "Stop using here" needs, and only a character read gives. A character whose
// owner could not be read is left out of the map, and gets no button rather
// than a guess.
export async function loadSeatOwners(
  tenantId: string,
  me: Pick<MeOut, 'players'>,
): Promise<Map<string, string | null>> {
  const owners = new Map<string, string | null>();
  const characterIds = new Set(
    me.players
      .filter((p) => p.tenant_id === tenantId)
      .flatMap((p) => p.characters.map((c) => c.entity_id)),
  );
  await Promise.all(
    [...characterIds].map(async (characterId) => {
      try {
        owners.set(characterId, (await getCharacter(tenantId, characterId)).owner_player_id);
      } catch {
        // Unknown: no button for it, rather than a guess.
      }
    }),
  );
  return owners;
}

// RFC 0014's roster-reuse sub-slice: bring an existing character from another
// campaign in the same library into this one, instead of creating a new one -
// only meaningful before the player has any character here yet.
function renderReuseForm(
  player: PlayerContextOut,
  reusable: CharacterSummaryOut[],
  onLinked: () => void,
): HTMLElement {
  const container = document.createElement('div');
  const label = document.createElement('p');
  label.textContent = 'Or use one of your existing characters in this library:';
  container.append(label);

  const list = document.createElement('ul');
  list.className = 'list';
  for (const character of reusable) {
    const item = document.createElement('li');
    const nameEl = document.createElement('span');
    nameEl.textContent = character.name;
    const useButton = document.createElement('button');
    useButton.type = 'button';
    useButton.textContent = 'Use this character';
    const status = createStatusSpan();
    useButton.addEventListener('click', async () => {
      status.textContent = 'Linking…';
      try {
        await linkCharacterToPlayer(player.tenant_id, character.entity_id, player.id);
        onLinked();
      } catch (e) {
        showError(status, e);
      }
    });
    item.append(nameEl, useButton, status);
    list.append(item);
  }
  container.append(list);
  return container;
}

// RFC 0017 (c) - removes this specific player row (and every character link it
// grants); other players' own roster-reuse links to this campaign are
// unaffected.
function renderLeaveButton(
  player: PlayerContextOut,
  campaign: CampaignSummaryOut,
  onLeft: () => void,
): HTMLElement {
  const container = document.createElement('div');
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Leave this campaign';
  const status = createStatusSpan();
  button.addEventListener('click', async () => {
    const confirmed = window.confirm(
      `Leave "${campaign.name}"? This removes every character link this grants you here - it can't be undone from this page.`,
    );
    if (!confirmed) return;
    status.textContent = 'Leaving…';
    try {
      await leaveCampaign(player.tenant_id, campaign.id, player.id);
      onLeft();
    } catch (e) {
      showError(status, e);
    }
  });
  container.append(button, status);
  return container;
}

// A seat's own subsection. There is no self-service join (RFC 0014 -
// POST .../players is can_manage_campaign-gated), so this is only ever drawn for
// a campaign you already hold a seat in.
export function renderSeat(
  campaign: CampaignSummaryOut,
  libraryName: string,
  player: PlayerContextOut,
  me: MeOut,
  owners: Map<string, string | null>,
  onChanged: () => void,
): HTMLElement {
  const section = document.createElement('section');
  section.className = 'campaign-subsection';
  const heading = document.createElement('h3');
  heading.textContent = campaign.name;
  const where = document.createElement('span');
  where.className = 'campaign-meta';
  where.textContent = ` in ${libraryName}`;
  heading.append(where);
  section.append(heading);

  if (player.characters.length === 0) {
    const none = document.createElement('p');
    none.textContent = "You don't have a character here yet.";
    section.append(none);
  } else {
    const list = document.createElement('ul');
    list.className = 'list';
    for (const character of player.characters) {
      // "Stop using here" is the reverse of reusing a character from another
      // campaign (ADR 0170), so it is only offered for a link that isn't the
      // character's own owner's: control comes from the links, and an owner
      // who unlinked themselves would lose their character. An owner that
      // couldn't be read leaves the button out.
      const owner = owners.get(character.entity_id);
      const extras =
        owner !== undefined && owner !== player.id
          ? [
              renderUnlinkCharacter(
                {
                  tenantId: player.tenant_id,
                  characterId: character.entity_id,
                  characterName: character.name,
                  playerId: player.id,
                  campaignName: campaign.name,
                },
                onChanged,
              ),
            ]
          : [];
      list.append(
        renderRenameableItem(
          character.name,
          (newName) =>
            updateCharacter(player.tenant_id, character.entity_id, { name: newName }).then(
              onChanged,
            ),
          extras,
        ),
      );
    }
    section.append(list);
  }

  section.append(
    renderCreateForm('New character name', 'Create character', (name) =>
      createCharacter(player.tenant_id, {
        name,
        owner_player_id: player.id,
        player_ids: [],
      }).then(onChanged),
    ),
  );

  if (player.characters.length === 0) {
    const reusable = reusableCharactersFor(me, player.tenant_id, campaign.id);
    if (reusable.length > 0) {
      section.append(renderReuseForm(player, reusable, onChanged));
    }
  }

  section.append(renderLeaveButton(player, campaign, onChanged));
  return section;
}
